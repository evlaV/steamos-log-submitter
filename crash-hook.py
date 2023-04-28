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
import steamos_log_submitter as sls
import time

logging.basicConfig(filename=f'{sls.base}/crash-hook.log', encoding='utf-8', level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

try:
    P, e, u, g, s, t, c, h, f, E = sys.argv[1:]

    logger.info(f'Process {P} ({e}) dumped core with signal {s} at {time.ctime(int(t))}')
    appid = sls.util.get_appid(int(P))
    minidump = f'{sls.pending}/minidump/{t}-{e}-{P}-{appid}.dmp'
    breakpad = subprocess.Popen(['/usr/lib/breakpad/core_handler', P, minidump], stdin=subprocess.PIPE)
    systemd = subprocess.Popen(['/usr/lib/systemd/systemd-coredump', P, u, g, s, t, c, h], stdin=subprocess.PIPE)

    while True:
        buffer = sys.stdin.buffer.read(4096)
        if not buffer:
            break
        try:
            breakpad.stdin.write(buffer)
        except Exception:
            pass
        try:
            systemd.stdin.write(buffer)
        except Exception:
            pass

    try:
        breakpad.stdin.close()
    except Exception:
        pass
    try:
        breakpad.wait(5)
    except Exception:
        pass

    try:
        systemd.stdin.close()
    except Exception:
        pass
    try:
        systemd.wait(5)
    except Exception:
        pass

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
    sls.trigger()
except Exception as e:
    logger.critical('Unhandled exception', exc_info=e)
