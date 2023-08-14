# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import io
import time
import zipfile
import steamos_log_submitter.crash as crash
from typing import TextIO
from . import Helper, HelperResult


class KdumpHelper(Helper):
    valid_extensions = frozenset({'.zip'})

    @staticmethod
    def get_summaries(dmesg: TextIO) -> tuple[str, str]:
        crash_summary_list: list[str] = []
        call_trace_list: list[str] = []
        call_trace_grab = 0

        # Extract only the lines between "Kernel panic -" and
        # "Kernel Offset:" / "Sending NMI" into the crash summary, and
        # the subset of those lines after " Call Trace:" and until the
        # 2nd "RIP:" into the call trace log - notice we remove the useless
        # lines like "Call Trace / <TASK>" and "Sending NMI / Kernel Offset".
        for line in dmesg:
            if crash_summary_list or 'Kernel panic -' in line:
                crash_summary_list.append(line)

                if call_trace_grab:
                    call_trace_list.append(line)
                    if ' RIP:' in line:
                        call_trace_grab -= 1
                elif ' Call Trace:' in line:
                    call_trace_grab = 2

                if 'Kernel Offset:' in line or 'Sending NMI' in line:
                    crash_summary_list.pop()
                    break

        crash_summary = ''.join(crash_summary_list)

        if call_trace_list:
            call_trace_list = call_trace_list[1:-1]
        call_trace = ''.join(call_trace_list)
        return crash_summary, call_trace

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        note, stack = None, None
        try:
            with zipfile.ZipFile(fname) as f:
                for zname in f.namelist():
                    if not zname.startswith('dmesg'):
                        continue
                    with io.TextIOWrapper(f.open(zname)) as dmesg:
                        note, stack = cls.get_summaries(dmesg)
                        if note:
                            break
        except zipfile.BadZipFile:
            return HelperResult(HelperResult.PERMANENT_ERROR)
        except OSError:
            return HelperResult(HelperResult.TRANSIENT_ERROR)

        if note is None or stack is None:
            return HelperResult(HelperResult.PERMANENT_ERROR)

        info = {
            'crash_time': int(time.time()),
            'stack': stack,
            'note': note,
        }
        return HelperResult.check(await crash.upload(product='holo', info=info, dump=fname))
