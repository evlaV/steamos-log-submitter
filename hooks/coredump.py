#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import os
import shutil
import subprocess
import sys
import time

import steamos_log_submitter as sls
import steamos_log_submitter.client
import steamos_log_submitter.helpers
from steamos_log_submitter.lockfile import LockHeldError, LockRetry
from steamos_log_submitter.logging import reconfigure_logging

reconfigure_logging(f'{sls.base}/crash-hook.log')
logger = logging.getLogger(__name__)


def tee(infd, outprocs):
    while True:
        buffer = infd.read(4096)
        if not buffer:
            break
        for proc in outprocs:
            try:
                proc.stdin.write(buffer)
            except Exception:
                pass

    for proc in outprocs:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(5)
        except Exception:
            pass


try:
    P, e, u, g, s, t, c, h, f, E = sys.argv[1:]

    logger.info(f'Process {P} ({e}) dumped core with signal {s} at {time.ctime(int(t))}')
    appid = sls.util.get_appid(int(P))
    minidump = f'{sls.pending}/minidump/{t}-{e}-{P}-{appid}.dmp'
    systemd = subprocess.Popen(['/usr/lib/systemd/systemd-coredump', P, u, g, s, t, c, h], stdin=subprocess.PIPE)
    try:
        with LockRetry(sls.helpers.lock('minidump'), 50):
            breakpad = subprocess.Popen(['/usr/lib/breakpad/core_handler', P, minidump], stdin=subprocess.PIPE)

            tee(sys.stdin.buffer, (breakpad, systemd))

            if breakpad.returncode:
                logger.error(f'Breakpad core_handler failed with status {breakpad.returncode}')
            if systemd.returncode:
                logger.error(f'systemd-coredump failed with status {systemd.returncode}')

            try:
                os.setxattr(minidump, 'user.executable', f.encode())
                os.setxattr(minidump, 'user.comm', e.encode())
                os.setxattr(minidump, 'user.path', E.replace('!', '/').encode())
            except OSError as e:
                logger.warning('Failed to set xattrs', exc_info=e)

            shutil.chown(minidump, user='steamos-log-submitter')
    except LockHeldError:
        logger.error("Couldn't claim minidump lockfile, giving up")
        tee(sys.stdin.buffer, (systemd,))

    with sls.util.drop_root():
        try:
            sls.client.Client().trigger()
        except FileNotFoundError:
            logger.info('Cannot trigger submission as the daemon does not appear to be active')
except Exception as e:
    logger.critical('Unhandled exception', exc_info=e)
