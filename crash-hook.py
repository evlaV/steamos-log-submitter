#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import shutil
import subprocess
import sys
import steamos_log_submitter as sls

logger = logging.getLogger(__name__)

try:
    P, e, u, g, s, t, c, h = sys.argv[1:]

    appid = sls.util.get_appid(int(P))
    minidump = f'{sls.pending}/minidump/{e}-{P}-{appid}.dmp'
    breakpad = subprocess.Popen(['/usr/lib/core_handler', P, minidump], stdin=subprocess.PIPE)
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

    shutil.chown(minidump, user='steamos-log-submitter')
    sls.trigger()
except Exception as e:
    logger.critical('Unhandled exception', exc_info=e)

# vim:ts=4:sw=4:et
