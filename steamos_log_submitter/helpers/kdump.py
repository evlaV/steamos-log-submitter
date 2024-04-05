# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import calendar
import io
import os
import re
import time
import typing
import zipfile
from typing import Optional, TextIO
from . import Helper, HelperResult

import steamos_log_submitter as sls
from steamos_log_submitter.sentry import SentryEvent
from steamos_log_submitter.types import JSONEncodable


class KdumpHelper(Helper):
    valid_extensions = frozenset({'.zip'})
    strip_re = re.compile(r'^(?:<\d>)?\[\s*\d+\.\d+\] ')
    frame_re = re.compile(r'(?P<q>\? )?(?:[0-9a-f]{4}:)?(?P<symbol>[_a-zA-Z][_a-zA-Z0-9.]*)\+(?P<offset>0x[0-9a-f]+)/(?P<size>0x[0-9a-f]+)(?: \[(?P<module>[_a-zA-Z0-9]+)(?: [0-9a-f]+)?\])?')
    rsp_re = re.compile(r'RSP: [0-9a-f]{4}:([0-9a-f]{16})')
    registers_re = re.compile(r'\b([A-Z0-9]{2,3}): *([0-9a-f]{4,16})')

    @classmethod
    def get_summaries(cls, dmesg: TextIO) -> tuple[str, list[dict[str, JSONEncodable]], dict[str, JSONEncodable]]:
        crash_summary_list: list[str] = []
        call_trace_list: list[str] = []
        metadata: dict[str, JSONEncodable] = {}
        call_trace_grab: Optional[str] = None
        getting_modules = False

        first_lines = (
            'Kernel panic -',
            'BUG: unable to handle page fault for address',
            'PREEMPT SMP NOPTI',
            'general protection fault',
        )

        trace_types = ('TASK', 'IRQ')

        # Extract only the lines between one of the starting prompts and
        # "Kernel Offset:" / "Sending NMI" into the crash summary, and
        # the subset of those lines after " <TASK>" and until the " </TASK>"
        # into the call trace log - notice we remove the useless lines
        # like "Call Trace / <TASK>" and "Sending NMI / Kernel Offset".
        for line in dmesg:
            start = False
            if not crash_summary_list:
                for check in first_lines:
                    if check in line:
                        start = True
                        break
            if crash_summary_list or start:
                crash_summary_list.append(line)

                if call_trace_grab:
                    if f' </{call_trace_grab}>' in line:
                        call_trace_grab = None
                    else:
                        call_trace_list.append(line)
                else:
                    for type in trace_types:
                        if f' <{type}>' in line:
                            call_trace_grab = type

                if 'Kernel Offset:' in line or 'Sending NMI' in line:
                    crash_summary_list.pop()
                    break
            if 'Modules linked in: ' in line:
                getting_modules = True
                line = line.split('Modules linked in:', 1)[1]
                metadata['kernel.modules'] = []
            if getting_modules:
                line = cls.strip_re.sub('', line.strip())
                if line.startswith('---') or line.startswith('Unloaded tainted modules:') or line.startswith('CR2:'):
                    getting_modules = False
                    continue
                typing.cast(list, metadata['kernel.modules']).extend(line.strip().split(' '))

        crash_summary = ''.join(cls.strip_re.sub('', line) for line in crash_summary_list)

        call_trace: list[dict[str, JSONEncodable]] = []
        if call_trace_list:
            call_trace = cls.parse_traces(call_trace_list[0:-1])
        if 'kernel.modules' in metadata:
            typing.cast(list, metadata['kernel.modules']).sort()
        return crash_summary, call_trace, metadata

    @classmethod
    def parse_traces(cls, log: list[str]) -> list[dict[str, JSONEncodable]]:
        traces: list[dict[str, JSONEncodable]] = []
        frames: Optional[list[dict[str, str]]] = None
        registers: Optional[dict[str, str]] = None

        ignore_frames = (
            'asm_exc_page_fault',
            'dump_stack_lvl',
            'panic',
        )

        def append(frames: list[dict[str, str]], regsiters: Optional[dict[str, str]]) -> None:
            frames.reverse()
            if registers:
                traces.append({
                    'frames': frames,
                    'registers': registers
                })
            else:
                traces.append({
                    'frames': frames,
                })

        for line in log:
            line = cls.strip_re.sub('', line.strip())
            frame = cls.frame_re.search(line)
            if line.startswith('RIP: '):
                if frames:
                    append(frames, registers)
                frames = None
                registers = None

            if frame:
                if frame.group('q'):
                    continue
                if not frames and frame.group('symbol').startswith('__'):
                    continue
                if frame.group('symbol') in ignore_frames:
                    frames = []
                    continue
                frame_info = {
                    'function': frame.group('symbol'),
                    'instruction_addr': frame.group('offset'),
                    'addr_mode': 'rel'
                }
                if frame.group('module'):
                    frame_info['package'] = frame.group('module')

                if not frames:
                    frames = []
                frames.append(frame_info)
                continue

            rsp = cls.rsp_re.search(line)
            if rsp:
                if not registers:
                    registers = {}
                registers['rsp'] = "0x" + rsp.group(1)
                continue

            registers_matches = cls.registers_re.findall(line)
            if registers_matches:
                if not registers:
                    registers = {}
                for reg, addr in registers_matches:
                    registers[reg.lower()] = "0x" + addr
                continue

        if frames:
            append(frames, registers)
        return traces

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        name, _ = os.path.splitext(os.path.basename(fname))
        stack = None
        event = SentryEvent(cls.config['dsn'])
        try:
            with zipfile.ZipFile(fname) as f:
                for zname in f.namelist():
                    with f.open(zname) as zf:
                        data = zf.read()
                        event.add_attachment({
                            'mime-type': 'text/plain',
                            'filename': zname,
                            'data': data
                        })
                        if zname.startswith('version'):
                            event.tags['kernel'] = data.decode().strip()
                        zf.seek(0)
                        if zname.startswith('build'):
                            with io.TextIOWrapper(zf) as build:
                                event.build_id = sls.util.get_build_id(build)
                        if zname.startswith('dmesg'):
                            with io.TextIOWrapper(zf) as dmesg:
                                event.message, stack, event.extra = cls.get_summaries(dmesg)
            with open(fname, 'rb') as f:
                attachment = f.read()
        except zipfile.BadZipFile:
            return HelperResult(HelperResult.PERMANENT_ERROR)
        except OSError:
            return HelperResult(HelperResult.TRANSIENT_ERROR)

        if event.message is None or stack is None:
            return HelperResult(HelperResult.PERMANENT_ERROR)

        t = time.strptime(name.split('-')[-1], '%Y%m%d%H%M')
        event.timestamp = calendar.timegm(t)
        event.add_attachment({
                'mime-type': 'application/zip',
                'filename': 'kdump.zip',
                'data': attachment
            })
        event.exceptions = [{'stacktrace': frames, 'type': 'PANIC'} for frames in stack]
        return HelperResult.check(await event.send())
