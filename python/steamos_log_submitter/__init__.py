import os
import re
import subprocess
from typing import Optional

__all__ = ['base', 'pending', 'get_appid', 'get_steam_account_id', 'trigger']

base = '/home/.steamos/offload/var/dump'
pending = f'{base}/pending'

def get_appid(pid : int) -> Optional[int]:
    appid = None
    stat_parse = re.compile(r'\d+\s+\((.*)\)\s+[A-Za-z]\s+(\d+)')

    while pid > 1:
        with open(f'/proc/{pid}/stat') as f:
            stat = f.read()

        stat_match = stat_parse.match(stat)
        comm = stat_match.group(1)
        ppid = int(stat_match.group(2))

        if comm == 'reaper':
            with open(f'/proc/{pid}/cmdline') as f:
                cmdline = f.read()

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


def get_steam_account_id() -> Optional[int]:
    import xdg
    import vdf
    share = xdg.xdg_data_home()

    try:
        with open(os.path.join(share, 'Steam', 'config', 'loginusers.vdf')) as v:
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

# vim:ts=4:sw=4:et
