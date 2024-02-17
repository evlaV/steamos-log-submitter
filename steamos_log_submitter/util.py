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
import subprocess
import time
from types import TracebackType
from typing import Optional, Type, Union

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


def get_appid(pid: int) -> Optional[int]:
    appid = None
    stat_parse = re.compile(r'\d+\s+\((.*)\)\s+[A-Za-z]\s+(\d+)')

    while pid > 1:
        try:
            with open(f'/proc/{pid}/environ') as f:
                env = {kv.split('=')[0]: kv.split('=', 1)[1] for kv in f.read().split('\0') if '=' in kv}
                if env:
                    try:
                        return int(env['SteamGameId'])
                    except (KeyError, ValueError):
                        pass
        except PermissionError:
            # Don't log a permission error; that just means we're not in a root context
            pass
        except OSError as e:
            logger.error(f'Failed to read /proc/{pid}/environ: {e}')
        try:
            with open(f'/proc/{pid}/stat') as f:
                stat = f.read()
        except OSError as e:
            logger.error(f'Failed to read /proc/{pid}/stat: {e}')
            return None

        stat_match = stat_parse.match(stat)
        if not stat_match:
            return None
        comm = stat_match.group(1)
        ppid = int(stat_match.group(2))

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
                    appid = int(arg[6:])
                elif arg == '--':
                    break

        pid = ppid
    return appid


def get_build_id(f: Optional[io.TextIOBase] = None) -> Optional[str]:
    try:
        if not f:
            f = open('/etc/os-release')
        for line in f:
            if '=' not in line:
                continue
            name, val = line.split('=', 1)
            if name == 'BUILD_ID':
                return val.strip()
    except OSError:
        pass
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
