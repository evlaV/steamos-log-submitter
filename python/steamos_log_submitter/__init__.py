import logging
import os
import subprocess
from .lockfile import Lockfile, LockHeldError
import steamos_log_submitter.util as util

__all__ = [
    # Constants
    'base',
    'scripts',
    'pending',
    'uploaded',
    # Utility functions
    'submit',
    'trigger',
    # Submodules
    'util',
]

base = '/home/.steamos/offload/var/steamos-log-submit'
scripts = '/usr/lib/steamos-log-submitter/scripts.d'
pending = f'{base}/pending'
uploaded = f'{base}/uploaded'

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
