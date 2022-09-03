import importlib
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

class HelperError(RuntimeError):
    pass


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


def create_helper(category):
    try:
        helper = importlib.import_module(f'steamos_log_submitter.helpers.{category}')
        def helper_fn(log) -> bool:
            if not getattr(helper, 'submit'):
                raise HelperError
            return helper.submit(log)
    except ModuleNotFoundError:
        helper = f'{scripts}/{category}'
        def helper_fn(log) -> bool:
            try:
                submission = subprocess.run([helper, log])
            except (FileNotFoundError, PermissionError) as exc:
                raise HelperError from exc
            return submission.returncode == 0
    return helper_fn


def submit():
    for category in os.listdir(pending):
        logs = os.listdir(f'{pending}/{category}')
        if not logs:
            continue

        try:
            with Lockfile(f'{pending}/{category}/.lock'):
                helper = create_helper(category)
                for log in logs:
                    if log.startswith('.'):
                        continue
                    try:
                        if helper(f'{pending}/{category}/{log}'):
                            os.replace(f'{pending}/{category}/{log}', f'{uploaded}/{category}/{log}')
                    except HelperError:
                        break
        except LockHeldError:
            # Another process is currently working on this directory
            continue

# vim:ts=4:sw=4:et
