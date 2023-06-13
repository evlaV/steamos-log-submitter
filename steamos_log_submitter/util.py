# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import grp
import logging
import os
import pwd
import re
import requests
import time
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = [
    'check_network',
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
        except OSError:
            return None

        stat_match = stat_parse.match(stat)
        comm = stat_match.group(1)
        ppid = int(stat_match.group(2))

        if comm == 'reaper':
            try:
                with open(f'/proc/{pid}/cmdline') as f:
                    cmdline = f.read()
            except OSError:
                return None

            cmdline = cmdline.split('\0')
            steam_launch = False
            for arg in cmdline:
                if arg == 'SteamLaunch':
                    steam_launch = True
                elif arg.startswith('AppId=') and steam_launch:
                    appid = int(arg[6:])
                elif arg == '--':
                    break

        pid = ppid
    return appid


def get_build_id() -> Optional[str]:
    with open('/etc/os-release') as f:
        for line in f:
            if '=' not in line:
                continue
            name, val = line.split('=', 1)
            if name == 'BUILD_ID':
                return val.strip()
    return None


def check_network() -> bool:
    max_checks = 5
    for _ in range(max_checks):
        try:
            r = requests.head('http://test.steampowered.com/204', allow_redirects=False, timeout=1)
            if r.status_code == 204:
                return True
        except Exception:
            pass
        time.sleep(4)

    return False


class drop_root:
    def __enter__(self):
        self.uid = os.geteuid()
        self.gid = os.getegid()

        uid = pwd.getpwnam('steamos-log-submitter')[2]
        gid = grp.getgrnam('steamos-log-submitter')[2]

        if self.uid == uid and self.gid == gid:
            return
        try:
            os.setegid(gid)
            os.seteuid(uid)
        except PermissionError as e:
            logger.error("Couldn't drop permissions", exc_info=e)
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            os.seteuid(self.uid)
            os.setegid(self.gid)
        except PermissionError as e:
            logger.error("Couldn't undrop permissions", exc_info=e)
        return False
