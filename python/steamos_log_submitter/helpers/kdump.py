#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import glob
import os
import sys
import time
from typing import Optional
import steamos_log_submitter as sls
from steamos_log_submitter.crash import upload as upload_crash

kdump_base = '/home/.steamos/offload/var/kdump/'
tmp_dir = f'{kdump_base}/.tmp'
logs_dir = f'{kdump_base}/logs'

def get_summaries() -> tuple[str, str]:
    crash_summary = []
    call_trace = []
    call_trace_grab = False
    dmesg = glob.glob(f'{tmp_dir}/dmesg*')
    with open(dmesg[0]) as f:
        # Extract only the lines between "Kernel panic -" and "Kernel Offset:" into the crash summary,
        # and the subset of those lines after " Call Trace:" and until " RIP:" into the call trace log
        for line in f:
            if crash_summary or 'Kernel panic -' in line:
                crash_summary.append(line)

                if call_trace_grab:
                    call_trace.append(line)
                    if ' RIP:' in line:
                        call_trace_grab = False
                elif ' Call Trace:' in line:
                    call_trace_grab = True

                if 'Kernel Offset:' in line:
                    break

    crash_summary = ''.join(crash_summary)
    call_trace = ''.join(call_trace)
    return crash_summary, call_trace


def get_build_id() -> Optional[str]:
    with open('/etc/os-release') as f:
        for line in f:
            name, val = line.split('=', 1)
            if name == 'BUILD_ID':
                return val.strip()
    return None


def collect() -> bool:
    serial = sls.util.get_deck_serial() or 'null'
    account = sls.util.get_steam_account_id()
    logs = glob.glob(f'{logs_dir}/*.zip')
    processed = 0
    for log in logs:
        stat = os.stat(f'{logs_dir}/{log}')
        if stat.st_size == 0:
            continue
        name = os.path.basename(log)[:-4]
        new_name = f'steamos-{name}_{serial}-{account}.zip'
        os.rename(log, f'{sls.pending}/kdump/{new_name}')
        processed += 1
    return processed > 0


def submit(fname : str) -> bool:
    name, ext = os.path.splitext(os.path.basename(fname))
    if ext != '.zip':
       return False

    note, stack = get_summaries()

    info = {
        'crash_time': int(time.time()),
        'stack': stack,
        'note': note,
    }
    if not upload_crash(product='holo', build=get_build_id(), version=os.uname().release, info=info, dump=fname):
        return False

    return True


if __name__ == '__main__':  # pragma: no cover
    try:
        sys.exit(0 if submit(sys.argv[1]) else 1)
    except:
        sys.exit(1)

# vim:ts=4:sw=4:et
