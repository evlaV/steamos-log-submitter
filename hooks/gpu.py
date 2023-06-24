#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import os
import shutil
import time
import steamos_log_submitter as sls
import steamos_log_submitter.helpers
from steamos_log_submitter.logging import reconfigure_logging

reconfigure_logging(f'{sls.base}/gpu-crash.log')
logger = logging.getLogger(__name__)

try:
    ts = time.time_ns()

    with sls.helpers.StagingFile('gpu', f'{ts}.log', 'w') as f:
        pid = None
        for key, val in os.environ.items():
            if key in ('PWD', '_'):
                continue
            if key == 'PID':
                pid = int(val)
            print(f'{key}={val}', file=f)
        if pid:
            appid = sls.util.get_appid(pid)
            if appid is not None:
                print(f'APPID={appid}', file=f)
        try:
            executable = os.path.basename(os.readlink(f'/proc/{pid}/exe'))
            print(f'EXE={executable}', file=f)
        except OSError:
            pass
        print(f'TIMESTAMP={ts}', file=f)
        shutil.chown(f.name, user='steamos-log-submitter')
except Exception as e:
    logger.critical('Unhandled exception', exc_info=e)
