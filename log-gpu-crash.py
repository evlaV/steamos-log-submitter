#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import os
import time
import steamos_log_submitter as sls

logging.basicConfig(filename=f'{sls.base}/gpu-crash.log', encoding='utf-8', level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

try:
    os.makedirs(f'{sls.pending}/gpu', mode=0o755, exist_ok=True)
    ts = time.time_ns()

    with open(f'{sls.pending}/gpu/{ts}.log', 'w') as f:
        pid = None
        for key, val in os.environ.items():
            if key in ('PWD', '_'):
                continue
            if key == 'PID':
                pid = int(val)
            print(f'{key}={val}', file=f)
        if pid:
            appid = sls.util.get_appid(pid)
            print(f'APPID={appid}', file=f)
        print(f'TIMESTAMP={ts}', file=f)

    sls.trigger()
except Exception as e:
    logger.critical('Unhandled exception', exc_info=e)
