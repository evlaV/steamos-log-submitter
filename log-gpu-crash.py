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

logging.basicConfig(filename=f'{sls.base}/gpu-crash.log', encoding='utf-8', level=logging.INFO, force=True)
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
            print(f'APPID={appid}', file=f)
        print(f'TIMESTAMP={ts}', file=f)
        shutil.chown(f.name, user='steamos-log-submitter')

    with sls.util.drop_root():
        sls.trigger()
except Exception as e:
    logger.critical('Unhandled exception', exc_info=e)
