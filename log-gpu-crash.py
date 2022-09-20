#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import os
import time
import steamos_log_submitter as sls

os.makedirs(f'{sls.pending}/gpu-crash', mode=0o755, exist_ok=True)
ts = time.time_ns()

with open(f'{sls.pending}/gpu-crash/{ts}.log', 'w') as f:
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

sls.trigger()

# vim:ts=4:sw=4:et
