# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import grp
import httpx
import logging
import os
import pwd
import re
import time
from types import TracebackType
from typing import Optional, Type, Union

logger = logging.getLogger(__name__)

__all__ = [
    'check_network',
    'drop_root',
    'get_appid',
    'get_build_id',
]


def get_appid(pid: int) -> Optional[int]:
    appid = None
    stat_parse = re.compile(r'\d+\s+\((.*)\)\s+[A-Za-z]\s+(\d+)')

    while pid > 1:
        try:
            with open(f'/proc/{pid}/stat') as f:
                stat = f.read()
        except OSError as e:
            logger.error(f'Failed to read /proc/{pid}/stat', exc_info=e)
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
                logger.error(f'Failed to read /proc/{pid}/cmdline', exc_info=e)
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


def get_build_id() -> Optional[str]:
    try:
        with open('/etc/os-release') as f:
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
        except PermissionError as e:
            logger.error("Couldn't drop permissions", exc_info=e)
            raise

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> bool:
        try:
            os.seteuid(self.uid)
            os.setegid(self.gid)
        except PermissionError as e:
            logger.error("Couldn't undrop permissions", exc_info=e)
        return not exc_type


def camel_case(text: str) -> str:
    def replace(match: re.Match) -> str:
        char = match.group(2)
        if char:
            return char.upper()
        return ''

    return re.sub('(^|_)([a-z])?', replace, text)


def snake_case(text: str) -> str:
    snaked = []
    for i, char in enumerate(text):
        if char.islower():
            snaked.append(char)
        else:
            if i:
                if snaked[-1].islower():
                    snaked.append('_')
                elif i + 1 < len(text) and text[i + 1].islower():
                    snaked.append('_')
            snaked.append(char)
    return ''.join(snaked).lower()
