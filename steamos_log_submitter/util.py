# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import grp
import hashlib
import httpx
import json
import logging
import io
import os
import pwd
import re
import sqlite3
import subprocess
import time
import typing
from elftools.elf.elffile import ELFFile
from types import TracebackType
from typing import Optional, Type, Union

import steamos_log_submitter as sls
from steamos_log_submitter.types import JSONEncodable

logger = logging.getLogger(__name__)

__all__ = [
    'camel_case',
    'check_network',
    'drop_root',
    'get_appid',
    'get_build_id',
    'get_steamos_branch',
    'snake_case',
    'telemetry_unit_id',
    'read_journal',
]


def get_pid_stat(pid: int) -> tuple[Optional[str], Optional[int]]:
    stat_parse = re.compile(r'\d+\s+\((.*)\)\s+[A-Za-z]\s+(\d+)')

    try:
        with open(f'/proc/{pid}/stat') as f:
            stat = f.read()
    except OSError as e:
        logger.error(f'Failed to read /proc/{pid}/stat: {e}')
        return None, None

    stat_match = stat_parse.match(stat)
    if not stat_match:
        return None, None
    comm = stat_match.group(1)
    ppid = int(stat_match.group(2))
    return comm, ppid


def get_appid(pid: int) -> Optional[int]:
    appid = None

    while pid > 1:
        try:
            with open(f'/proc/{pid}/environ') as f:
                env = {kv.split('=')[0]: kv.split('=', 1)[1] for kv in f.read().split('\0') if '=' in kv}
                if env:
                    try:
                        appid = int(env['SteamGameId'])
                        break
                    except (KeyError, ValueError):
                        pass
        except PermissionError:
            # Don't log a permission error; that just means we're not in a root context
            pass
        except OSError as e:
            logger.error(f'Failed to read /proc/{pid}/environ: {e}')

        comm, ppid = get_pid_stat(pid)
        if comm is None or ppid is None:
            return None
        if comm == 'reaper':
            try:
                with open(f'/proc/{pid}/cmdline') as f:
                    cmdline = f.read()
            except OSError as e:
                logger.error(f'Failed to read /proc/{pid}/cmdline: {e}')
                return None

            cmdline_args = cmdline.split('\0')
            steam_launch = False
            for arg in cmdline_args:
                if arg == 'SteamLaunch':
                    steam_launch = True
                elif arg.startswith('AppId=') and steam_launch:
                    try:
                        appid = int(arg[6:])
                    except ValueError:
                        return None
                elif arg == '--':
                    break

        pid = ppid
    if appid and appid >= 0x80000000:
        # This is a non-Steam game
        return None
    return appid


def get_file_key(key: str, f: io.TextIOBase) -> Optional[str]:
    try:
        for line in f:
            if '=' not in line:
                continue
            name, val = line.split('=', 1)
            if name == key:
                val = val.strip()
                if len(val) >= 2 and val[0] == val[-1] == '"':
                    val = val.strip('"')
                return val
    except OSError:
        pass
    return None


def get_version_id(f: Optional[io.TextIOBase] = None) -> Optional[str]:
    try:
        if not f:
            f = open('/etc/os-release')
        return get_file_key('VERSION_ID', f)
    except OSError:
        return None


def get_build_id(f: Optional[io.TextIOBase] = None) -> Optional[str]:
    try:
        if not f:
            f = open('/etc/os-release')
        return get_file_key('BUILD_ID', f)
    except OSError:
        return None


def check_network() -> bool:
    max_checks = 5
    for _ in range(max_checks):
        try:
            r = httpx.head('http://test.steampowered.com/204', follow_redirects=False, timeout=1)
            if r.status_code == 204:
                return True
        except Exception:
            pass
        time.sleep(4)

    return False


def telemetry_unit_id() -> Optional[str]:
    fingerprints = []

    try:
        with open('/sys/class/net/wlan0/address', 'rb') as f:
            fingerprints.append(b'mac:' + f.read().strip())
    except OSError:
        pass

    try:
        with open('/etc/machine-id', 'rb') as f:
            fingerprints.append(b'machine:' + f.read().strip())
    except OSError:
        return None

    if not fingerprints:
        return None

    hash = hashlib.blake2b(b'\0'.join(fingerprints), digest_size=16)
    return hash.hexdigest()


def get_steamos_branch() -> Optional[str]:
    try:
        result = subprocess.run(['/usr/bin/steamos-select-branch', '-c'], capture_output=True, errors='replace', check=True)
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError) as e:
        logger.warning('Failed to read SteamOS branch', exc_info=e)
    return None


class drop_root:
    def __init__(self, target_uid: Union[int, str] = 'steamos-log-submitter', target_gid: Union[int, str] = 'steamos-log-submitter'):
        if isinstance(target_uid, str):
            try:
                self.target_uid = int(target_uid)
            except ValueError:
                self.target_uid = pwd.getpwnam(target_uid)[2]

        if isinstance(target_gid, str):
            try:
                self.target_gid = int(target_gid)
            except ValueError:
                self.target_gid = grp.getgrnam(target_gid)[2]

    def __enter__(self) -> None:
        self.uid = os.geteuid()
        self.gid = os.getegid()

        if self.uid == self.target_uid and self.gid == self.target_gid:
            return
        try:
            os.setegid(self.target_gid)
            os.seteuid(self.target_uid)
        except PermissionError:
            logger.error("Couldn't drop permissions")
            raise

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> bool:
        try:
            os.seteuid(self.uid)
            os.setegid(self.gid)
        except PermissionError:
            logger.error("Couldn't undrop permissions")
        return not exc_type


def camel_case(text: str) -> str:
    def replace(match: re.Match) -> str:
        char: Optional[str] = match.group(2)
        if char:
            return char.upper()
        return ''

    return re.sub('(^|_)([a-z])?', replace, text)


def snake_case(text: str) -> str:
    snaked = []
    for i, char in enumerate(text):
        if char.isnumeric() or char.islower():
            snaked.append(char)
        else:
            if i:
                for j in range(1, len(snaked) + 1):
                    if snaked[-j].isalpha():
                        if snaked[-j].islower():
                            snaked.append('_')
                        break
                if snaked[-1].isalpha() and i + 1 < len(text) and text[i + 1].islower():
                    snaked.append('_')
            snaked.append(char)
    return ''.join(snaked).lower()


async def read_journal(unit: str, cursor: Optional[str] = None, *,
                       current_boot: bool = False,
                       start_ago_ms: Optional[int] = None) -> tuple[Optional[list[dict[str, JSONEncodable]]], Optional[str]]:
    cmd = ['journalctl', '-o', 'json']
    if unit == 'kernel':
        cmd.append('-k')
    else:
        cmd.extend(['-u', unit])
    if cursor is not None:
        cmd.extend(['--after-cursor', cursor])
    if current_boot:
        cmd.extend(['-b', '0'])
    if start_ago_ms is not None:
        cmd.extend(['-S', f'-{start_ago_ms}ms'])
    try:
        journal = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        assert journal.stdout is not None

        logs: list[dict[str, JSONEncodable]] = []
        cursor = None
        while True:
            line = await journal.stdout.readline()
            if not line:
                break
            log = json.loads(line.decode())
            logs.append(log)
            cursor = log['__CURSOR']
    except OSError as e:
        logger.error('Failed to exec journalctl', exc_info=e)
        return None, None

    return logs, cursor


def read_file(path: str, binary: bool = False) -> Union[bytes, str, None]:
    try:
        with open(path, 'rb' if binary else 'r') as f:
            data: bytes = f.read()
            if binary:
                return data
            return data.strip()
    except FileNotFoundError:
        return None


def get_exe_build_id(path: str) -> Optional[str]:
    try:
        with open(path, 'rb') as progf:
            elf = ELFFile(progf)
            for section in elf.iter_sections():
                if section.name != '.note.gnu.build-id':
                    continue
                if type(section).__name__ != 'NoteSection':
                    logger.warning(f'Correctly named section has wrong type {type(section).__name__}')
                    continue
                for note in section.iter_notes():
                    if note.n_type == 'NT_GNU_BUILD_ID':
                        return typing.cast(str, note.n_desc)
                break
    except OSError as e:
        logger.warning('Failed to get buildid', exc_info=e)
    return None


def get_path_package(path: str) -> Optional[tuple[str, str]]:
    try:
        package = subprocess.run(['/usr/bin/pacman', '-Qo', path], capture_output=True, errors='replace')
        if package.returncode == 0:
            pkgname, pkgver = package.stdout.strip().split(' ')[-2:]
            return pkgname, pkgver
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning('Failed to get package', exc_info=e)
    return None


async def update_app_list() -> bool:
    ua_string = f'SteamOS Log Submitter/{sls.__version__}'

    logger.debug('Updating app list')
    async with httpx.AsyncClient() as client:
        try:
            get = await client.get('https://api.steampowered.com/ISteamApps/GetAppList/v2/?format=json', headers={
                'User-Agent': ua_string
            })
        except httpx.HTTPError as e:
            logger.warning('Exception occurred while fetching app list', exc_info=e)
            return False

        if get.status_code != 200:
            logger.warning(f'Failed to fetch app list with status code {get.status_code}')
            return False

        try:
            applist_raw = get.json()["applist"]["apps"]
        except (KeyError, json.decoder.JSONDecodeError) as e:
            logger.warning('Failed to parse app list', exc_info=e)
            return False

    db = sqlite3.connect(f'{sls.data.data_root}/applist.sqlite3')
    cursor = db.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS applist (
        appid INTEGER,
        name TEXT,
        PRIMARY KEY (appid)
    )''')

    for app in applist_raw:
        cursor.execute('INSERT OR REPLACE INTO applist (appid, name) VALUES (:appid, :name)', app)
    db.commit()

    cursor.execute('VACUUM')
    logger.info('App list updated')
    return True


def get_app_name(appid: int) -> Optional[str]:
    try:
        db = sqlite3.connect(f'{sls.data.data_root}/applist.sqlite3')
    except sqlite3.OperationalError as e:
        logger.warning(f'Failed to open app list database: {e}')
        return None

    cursor = db.cursor()
    try:
        cursor.execute('SELECT name FROM applist WHERE appid = :appid', {'appid': appid})
    except sqlite3.OperationalError:
        return None
    row = cursor.fetchone()
    if row is None:
        return None
    return typing.cast(str, row[0])


def get_dmi_info() -> dict[str, str]:
    products: dict[str, dict[str, str]] = {
        'AOKZOE': {
            'AOKZOE A1 AR07': 'AOKZOE A1',
            'AOKZOE A1 Pro': 'AOKZOE A1 Pro',
            'AOKZOE A1X': 'AOKZOE A1X',
        },
        'ASUSTeK COMPUTER INC.': {
            'RC71L': 'ROG Ally',
            'RC72LA': 'ROG Ally X',
        },
        'AYANEO': {
            'AYA NEO 2021': 'AYANEO 2021',
            'AYANEO 2021': 'AYANEO 2021',
            'AYANEO 2021 Pro': 'AYANEO 2021 Pro',
            'AYANEO 2021 Pro Retro Power': 'AYANEO 2021 Pro',
            'AYANEO 2': 'AYANEO 2',
            'GEEK': 'AYANEO GEEK',
            'AYANEO 2S': 'AYANEO 2S',
            'GEEK 1S': 'AYANEO GEEK 1S',
            'AYANEO GEEK 1S': 'AYANEO GEEK 1S',
            'AIR': 'AYANEO AIR',
            'AIR Pro': 'AYANEO AIR Pro',
            'AIR 1S': 'AYANEO AIR 1S',
            'AB05-AMD': 'AYANEO AIR Plus AMD',
            'AB05-Intel': 'AYANEO AIR Plus Intel',
            'AB05-Mendocino': 'AYANEO AIR Plus Mendocino',
            'FLIP DS': 'AYANEO FLIP',
            'FLIP KB': 'AYANEO FLIP',
            'AYANEO KUN': 'AYANEO KUN',
            'NEXT': 'AYANEO NEXT',
            'AYANEO NEXT': 'AYANEO NEXT',
            'NEXT Advance': 'AYANEO NEXT Advance',
            'AYANEO NEXT Advance': 'AYANEO NEXT Advance',
            'NEXT Lite': 'AYANEO NEXT Lite',
            'NEXT Pro': 'AYANEO NEXT Pro',
            'AYANEO NEXT Pro': 'AYANEO NEXT Pro',
            'SLIDE': 'AYANEO SLIDE',
        },
        'AYA NEO': {
            'AYA NEO FOUNDER': 'AYANEO 2021',
        },
        'ayn': {
            'Loki Max': 'Ayn Loki Max',
            'Loki MiniPro': 'Ayn Loki MiniPro',
            'Loki Zero': 'Ayn Loki Zero',
        },
        'GPD': {
            'G1618-03': 'GPD WIN 3',
            'G1618-04': 'GPD WIN 4',
            'G1619-04': 'GPD WIN Max 2',
            'G1617-01': 'GPD WIN Mini',
        },
        'LENOVO': {
            '83E1': 'Legion Go',
            '83L3': 'Legion Go S',
            '83N6': 'Legion Go S',
            '83Q2': 'Legion Go S',
            '83Q3': 'Legion Go S',
            '83N0': 'Legion Go 2',
            '83N1': 'Legion Go 2',
        },
        'Micro-StarInternationalCo.,Ltd.': {
            'ClawA1M': 'MSI Claw A1M',
            'Claw7AI+A2VM': 'MSI Claw 7 AI+ A2VM',
            'Claw8AI+A2VM': 'MSI Claw 8 AI+ A2VM',
            'ClawA8BZ2EM': 'MSI Claw A8 BZ2EM',
        },
        'ONE-NETBOOK': {
            'ONEXPLAYER 2 ARP23': 'ONEXPLAYER 2',
            'ONEXPLAYER 2 PRO ARP23': 'ONEXPLAYER 2 Pro',
            'ONEXPLAYER 2 PRO ARP23 EVA-01': 'ONEXPLAYER 2 Pro',
            'ONEXPLAYER F1': 'ONEXPLAYER OneXFly F1',
            'ONEXPLAYER F1Pro': 'ONEXPLAYER OneXFly F1 Pro',
            'ONEXPLAYER Mini Pro': 'ONEXPLAYER Mini Pro',
        },
        'ZOTAC': {
            'G0A1W': 'ZONE',
        },
    }
    info: dict[str, str] = {}
    sys_vendor = sls.util.read_file('/sys/class/dmi/id/sys_vendor')
    board_name = sls.util.read_file('/sys/class/dmi/id/board_name')
    product_name = sls.util.read_file('/sys/class/dmi/id/product_name')
    lookup_table = {
        'AOKZOE': product_name,
        'ASUSTeK COMPUTER INC.': board_name,
        'AYA NEO': product_name,
        'AYANEO': product_name,
        'ayn': product_name,
        'GPD': product_name,
        'LENOVO': product_name,
        'Micro-StarInternationalCo.,Ltd.': product_name,
        'ONE-NETBOOK': product_name,
        'ZOTAC': board_name,
    }
    assert sys_vendor is None or isinstance(sys_vendor, str)
    assert board_name is None or isinstance(board_name, str)
    assert product_name is None or isinstance(product_name, str)
    if sys_vendor == 'Valve':
        bios_version = sls.util.read_file('/sys/class/dmi/id/bios_version')
        assert bios_version is None or isinstance(bios_version, str)
        info['vendor'] = sys_vendor
        if bios_version:
            info['bios'] = bios_version
        if product_name:
            info['product'] = product_name
    elif sys_vendor is not None and sys_vendor in products:
        lookup = lookup_table.get(sys_vendor)
        if lookup is not None and lookup in products[sys_vendor]:
            assert isinstance(lookup, str)
            info['vendor'] = sys_vendor
            info['product'] = products[sys_vendor][lookup]
        elif product_name in products[sys_vendor]:
            info['vendor'] = sys_vendor
            info['product'] = products[sys_vendor][product_name]
        elif board_name in products[sys_vendor]:
            info['vendor'] = sys_vendor
            info['product'] = products[sys_vendor][board_name]
    return info
