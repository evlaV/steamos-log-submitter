import logging
import os
import pwd
import re
import requests
import subprocess
import time
import vdf
from typing import Optional
from .lockfile import Lockfile, LockHeldError

__all__ = [
    # Constants
    'base',
    'scripts',
    'pending',
    'uploaded',
    # Utility functions
    'check_network',
    'get_appid',
    'get_deck_serial',
    'get_steam_account_id',
    'submit',
    'trigger',
]

base = '/home/.steamos/offload/var/steamos-log-submit'
scripts = '/usr/lib/steamos-log-submitter/scripts.d'
pending = f'{base}/pending'
uploaded = f'{base}/uploaded'

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


def get_appid(pid : int) -> Optional[int]:
    appid = None
    stat_parse = re.compile(r'\d+\s+\((.*)\)\s+[A-Za-z]\s+(\d+)')

    while pid > 1:
        try:
            with open(f'/proc/{pid}/stat') as f:
                stat = f.read()
        except:
            return None

        stat_match = stat_parse.match(stat)
        comm = stat_match.group(1)
        ppid = int(stat_match.group(2))

        if comm == 'reaper':
            try:
                with open(f'/proc/{pid}/cmdline') as f:
                    cmdline = f.read()
            except:
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


def get_deck_serial(uid : int = 1000) -> Optional[str]:
    home = pwd.getpwuid(uid).pw_dir

    try:
        with open(f'{home}/.local/share/Steam/config/config.vdf') as v:
            config = vdf.load(v)
    except:
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
        with open(f'{home}/.local/share/Steam/config/loginusers.vdf') as v:
            loginusers = vdf.load(v)
    except:
        return None

    if 'users' not in loginusers:
        return None

    for userid, data in loginusers['users'].items():
        if data.get('MostRecent', '0') == '1':
            return int(userid)

    return None


def trigger():
    systemctl = subprocess.Popen(['/usr/bin/systemctl', 'show', 'steamos-log-submitter.timer'], stdout=subprocess.PIPE)
    for line in systemctl.stdout:
        if not line.startswith(b'ActiveState='):
            continue
        # Do not trigger the submitter if the timer is disabled
        if line == b'ActiveState=active\n':
            subprocess.Popen(['/usr/bin/systemctl', 'start', 'steamos-log-submitter.service'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        break
    systemctl.stdout.close()
    try:
        systemctl.wait(1)
    except:
        pass


def submit():
    for category in os.listdir(pending):
        logs = os.listdir(f'{pending}/{category}')
        if not logs:
            continue

        try:
            with Lockfile(f'{pending}/{category}/.lock'):
                helper = f'{scripts}/{category}'
                for log in logs:
                    if log.startswith('.'):
                        continue
                    try:
                        submission = subprocess.run([helper, f'{pending}/{category}/{log}'])
                    except (FileNotFoundError, PermissionError):
                        break
                    if submission.returncode == 0:
                        os.replace(f'{pending}/{category}/{log}', f'{uploaded}/{category}/{log}')
        except LockHeldError:
            # Another process is currently working on this directory
            continue

# vim:ts=4:sw=4:et
