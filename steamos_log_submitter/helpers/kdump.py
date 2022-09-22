# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import io
import logging
import os
import sys
import time
import zipfile
from typing import TextIO
import steamos_log_submitter as sls
from steamos_log_submitter.crash import upload as upload_crash

def get_summaries(dmesg : TextIO) -> tuple[str, str]:
    crash_summary = []
    call_trace = []
    call_trace_grab = False

    # Extract only the lines between "Kernel panic -" and "Kernel Offset:" into the crash summary,
    # and the subset of those lines after " Call Trace:" and until " RIP:" into the call trace log
    for line in dmesg:
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


def collect() -> bool:
    return False


def submit(fname : str) -> bool:
    name, ext = os.path.splitext(os.path.basename(fname))
    if ext != '.zip':
       return False

    note, stack = None, None
    try:
        with zipfile.ZipFile(fname) as f:
            for zname in f.namelist():
                if not zname.startswith('dmesg'):
                    continue
                with io.TextIOWrapper(f.open(zname)) as dmesg:
                    note, stack = get_summaries(dmesg)
    except (zipfile.BadZipFile, IOError):
        return False

    if note is None or stack is None:
        return False

    info = {
        'crash_time': int(time.time()),
        'stack': stack,
        'note': note,
    }
    if not upload_crash(product='holo', build=sls.util.get_build_id(), version=os.uname().release, info=info, dump=fname):
        return False

    return True

# vim:ts=4:sw=4:et
