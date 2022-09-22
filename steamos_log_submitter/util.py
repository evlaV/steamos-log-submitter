# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import pwd
import re
import requests
import time
import vdf
from typing import Optional

__all__ = [
    'check_network',
    'get_appid',
    'get_deck_serial',
    'get_steam_account_id',
]

def get_appid(pid : int) -> Optional[int]:
    appid = None
    stat_parse = re.compile(r'\d+\s+\((.*)\)\s+[A-Za-z]\s+(\d+)')

    while pid > 1:
        try:
            with open(f'/proc/{pid}/stat') as f:
                stat = f.read()
        except IOError:
            return None

        stat_match = stat_parse.match(stat)
        comm = stat_match.group(1)
        ppid = int(stat_match.group(2))

        if comm == 'reaper':
            try:
                with open(f'/proc/{pid}/cmdline') as f:
                    cmdline = f.read()
            except IOError:
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


def get_deck_serial(uid : int = 1000) -> Optional[str]:
    home = pwd.getpwuid(uid).pw_dir

    try:
        with open(f'{home}/.steam/root/config/config.vdf') as v:
            config = vdf.load(v)
    except (IOError, SyntaxError):
        return None

    if 'InstallConfigStore' not in config:
        return None

    if 'SteamDeckRegisteredSerialNumber' not in config['InstallConfigStore']:
        return None

    serial = config['InstallConfigStore']['SteamDeckRegisteredSerialNumber']
    if type(serial) != str:
        return None
    return serial


def get_steam_account_id(uid : int = 1000) -> Optional[int]:
    home = pwd.getpwuid(uid).pw_dir

    try:
        with open(f'{home}/.steam/root/config/loginusers.vdf') as v:
            loginusers = vdf.load(v)
    except (IOError, SyntaxError):
        return None

    if 'users' not in loginusers:
        return None

    for userid, data in loginusers['users'].items():
        if data.get('MostRecent', '0') == '1':
            return int(userid)
        if data.get('mostrecent', '0') == '1':
            return int(userid)

    return None


def get_steam_account_name(uid : int = 1000) -> Optional[str]:
    home = pwd.getpwuid(uid).pw_dir

    try:
        with open(f'{home}/.steam/root/config/loginusers.vdf') as v:
            loginusers = vdf.load(v)
    except (IOError, SyntaxError):
        return None

    if 'users' not in loginusers:
        return None

    for data in loginusers['users'].values():
        if data.get('MostRecent', '0') == '1':
            return data.get('AccountName')
        if data.get('mostrecent', '0') == '1':
            return data.get('AccountName')

    return None


def check_network() -> bool:
    max_checks = 5
    for _ in range(max_checks):
        try:
            r = requests.head('http://test.steampowered.com/204', allow_redirects=False, timeout=1)
            if r.status_code == 204:
                return True
        except:
            pass
        time.sleep(4)

    return False

# vim:ts=4:sw=4:et
