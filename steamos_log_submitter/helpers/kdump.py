# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import io
import logging
import os
import time
import zipfile
from typing import TextIO
from steamos_log_submitter.crash import upload as upload_crash

logger = logging.getLogger(__name__)


def get_summaries(dmesg: TextIO) -> tuple[str, str]:
    crash_summary = []
    call_trace = []
    call_trace_grab = 0

    # Extract only the lines between "Kernel panic -" and
    # "Kernel Offset:" / "Sending NMI" into the crash summary, and
    # the subset of those lines after " Call Trace:" and until the
    # 2nd "RIP:" into the call trace log - notice we remove the useless
    # lines like "Call Trace / <TASK>" and "Sending NMI / Kernel Offset".
    for line in dmesg:
        if crash_summary or 'Kernel panic -' in line:
            crash_summary.append(line)

            if call_trace_grab:
                call_trace.append(line)
                if ' RIP:' in line:
                    call_trace_grab -= 1
            elif ' Call Trace:' in line:
                call_trace_grab = 2

            if 'Kernel Offset:' in line or 'Sending NMI' in line:
                crash_summary.pop()
                break

    crash_summary = ''.join(crash_summary)

    if call_trace:
        call_trace.pop(0)
        call_trace.pop()
    call_trace = ''.join(call_trace)
    return crash_summary, call_trace


def collect() -> bool:
    return False


def submit(fname: str) -> bool:
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
                    if note:
                        break
    except (zipfile.BadZipFile, IOError):
        return False

    if note is None or stack is None:
        return False

    info = {
        'crash_time': int(time.time()),
        'stack': stack,
        'note': note,
    }
    return upload_crash(product='holo', info=info, dump=fname)
