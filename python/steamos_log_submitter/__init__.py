# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
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

base = '/home/.steamos/offload/var/steamos-log-submitter'
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
            submit()
        break
    systemctl.stdout.close()
    try:
        systemctl.wait(1)
    except:
        pass


class Helper:
    def __init__(self, category):
        self.category = category
        self._helper = f'{scripts}/{category}'

    def submit(self, log):
        try:
            submission = subprocess.run([self._helper, log])
        except (FileNotFoundError, PermissionError) as e:
            raise HelperError from e
        return submission.returncode == 0

    def collect(self):
        return False


def create_helper(category):
    try:
        helper = importlib.import_module(f'steamos_log_submitter.helpers.{category}')
        if not hasattr(helper, 'submit'):
            raise HelperError
    except ModuleNotFoundError:
        return Helper(category)
    return helper


def collect():
    for category in os.listdir(pending):
        try:
            with Lockfile(f'{pending}/{category}/.lock'):
                helper = create_helper(category)
                helper.collect()
        except LockHeldError:
            # Another process is currently working on this directory
            continue


def submit():
    for category in os.listdir(pending):
        logs = os.listdir(f'{pending}/{category}')
        if not logs:
            continue

        try:
            with Lockfile(f'{pending}/{category}/.lock'):
                try:
                    helper = create_helper(category)
                    for log in logs:
                        if log.startswith('.'):
                            continue
                        if helper.submit(f'{pending}/{category}/{log}'):
                            os.replace(f'{pending}/{category}/{log}', f'{uploaded}/{category}/{log}')
                except HelperError:
                    continue
        except LockHeldError:
            # Another process is currently working on this directory
            continue

# vim:ts=4:sw=4:et
