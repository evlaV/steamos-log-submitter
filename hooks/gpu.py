#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
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
    log = {
        'env': {},
        'timestamp': ts / 1_000_000_000,
        'kernel': os.uname().release,
        'branch': sls.steam.get_steamos_branch(),
    }
    pid = None
    for key, val in os.environ.items():
        if key == 'PID':
            pid = int(val)
        log['env'][key] = val
    if pid:
        log['pid'] = pid
        appid = sls.util.get_appid(pid)
        if appid is not None:
            log['appid'] = appid
    try:
        executable = os.path.basename(os.readlink(f'/proc/{pid}/exe'))
        log['executable'] = executable
    except OSError:
        pass
    with sls.helpers.StagingFile('gpu', f'{ts}.json', 'w') as f:
        json.dump(log, f)
        shutil.chown(f.name, user='steamos-log-submitter')
except Exception as e:
    logger.critical('Unhandled exception', exc_info=e)
