# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next as dbus
import enum
import json
import os
import re
import time
from collections.abc import Iterable
from typing import Final, Optional, Self

import steamos_log_submitter as sls
from steamos_log_submitter.aggregators.sentry import SentryEvent
from steamos_log_submitter.constants import DBUS_NAME
from steamos_log_submitter.types import DBusEncodable, JSONEncodable

from . import Helper, HelperResult


class TraceEvent:
    class Type(enum.StrEnum):
        OOM = enum.auto()
        SPLIT_LOCK = enum.auto()

    def __init__(self, type: Type, /):
        self.type = type
        self.appid: Optional[int] = None
        self.pid: Optional[int] = None
        self.timestamp = 0.0
        self.uptime = 0.0
        self.journal: Optional[list[str]] = None
        self.path: Optional[str] = None
        self.executable: Optional[str] = None
        self.comm: Optional[str] = None
        self.build_id: Optional[str] = None
        self.pkgname: Optional[str] = None
        self.pkgver: Optional[str] = None

    def to_json(self) -> str:
        data: dict[str, JSONEncodable] = {
            'type': self.type
        }
        if self.timestamp:
            data['timestamp'] = self.timestamp
        if self.uptime:
            data['uptime'] = self.uptime
        for attr in ('pid', 'appid', 'journal', 'path', 'executable', 'comm', 'build_id', 'pkgname', 'pkgver'):
            if getattr(self, attr) is not None:
                data[attr] = getattr(self, attr)
        return json.dumps(data)


class TraceHelper(Helper):
    valid_extensions = frozenset({'.json'})

    TIMING_BUFFER = 100000
    JOURNAL_STARTS: Final[dict[TraceEvent.Type, Iterable[re.Pattern]]] = {
        TraceEvent.Type.OOM: [re.compile('invoked oom-killer')],
        TraceEvent.Type.SPLIT_LOCK: [re.compile(r'x86/split lock detection: #AC: .{1,15}/\d+ .+ split_lock trap')],
    }

    JOURNAL_ENDS: Final[dict[TraceEvent.Type, Iterable[re.Pattern]]] = {
        TraceEvent.Type.OOM: [re.compile('Out of memory: Killed process')],
    }

    @classmethod
    def _setup(cls) -> None:
        super()._setup()
        cls.extra_ifaces.append(TraceInterface())

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        basename = os.path.basename(fname)
        event = SentryEvent(cls.config['dsn'])
        try:
            with open(fname, 'rb') as f:
                log = f.read()
        except OSError as e:
            cls.logger.error(f'Failed to open log file {basename}: {e}')
            return HelperResult.TRANSIENT_ERROR
        try:
            parsed_log = json.loads(log)
        except json.decoder.JSONDecodeError as e:
            cls.logger.error(f'Trace JSON {basename} failed to parse', exc_info=e)
            return HelperResult.PERMANENT_ERROR

        event.timestamp = parsed_log.get('timestamp')
        event.appid = parsed_log.get('appid')
        for attr in ('executable', 'comm', 'path', 'build_id', 'pkgname', 'pkgver'):
            if attr in parsed_log:
                event.tags[attr] = parsed_log[attr]

        event.add_attachment({
                'mime-type': 'application/json',
                'filename': 'trace.json',
                'data': log
            })
        if 'executable' in parsed_log:
            event.message = f'{parsed_log["type"]}: {parsed_log.get("executable")}'
        elif 'comm' in parsed_log:
            event.message = f'{parsed_log["type"]}: {parsed_log.get("comm")}'
        else:
            event.message = parsed_log['type']

        return HelperResult.check(await event.send())

    @classmethod
    async def prepare_event(cls, line: str, data: dict[str, DBusEncodable]) -> TraceEvent:
        trace = TraceLine(line)

        event = None
        if trace.function == 'mark_victim':
            if not trace.extra_args:
                raise ValueError('Invalid OOM event missing victim pid')
            if not trace.extra_args[0].startswith('pid='):
                raise ValueError(f'Invalid pid in {trace.extra_args[0]}')

            event = TraceEvent(TraceEvent.Type.OOM)
            event.pid = int(trace.extra_args[0].split('=', 1)[1])
        if trace.function == 'split_lock_warn':
            event = TraceEvent(TraceEvent.Type.SPLIT_LOCK)

        if event is None:
            raise ValueError

        event.timestamp = time.time()
        event.comm = trace.comm
        event.uptime = trace.timestamp
        if event.pid is None:
            event.pid = trace.pid

        if 'appid' in data:
            if not isinstance(data['appid'], int):
                raise ValueError
            event.appid = data['appid']

        if 'comm' in data:
            event.comm = str(data['comm'])

        if 'path' in data:
            event.path = str(data['path'])
            event.executable = os.path.basename(event.path)
            event.build_id = sls.util.get_exe_build_id(event.path)
            package = sls.util.get_path_package(event.path)
            if package:
                event.pkgname, event.pkgver = package

        if event.appid is None and event.pid is not None:
            event.appid = sls.util.get_appid(event.pid)

        event.journal = await cls.read_journal(event.type, int(event.uptime * 1_000_000))

        return event

    @classmethod
    async def read_journal(cls, type: TraceEvent.Type, start_usec: int) -> Optional[list[str]]:
        if type not in cls.JOURNAL_STARTS:
            return None

        cursor = cls.data.get(f'{type}.cursor')
        if cursor is not None:
            assert isinstance(cursor, str)
        lines, cursor = await sls.util.read_journal('kernel', cursor, current_boot=True)
        if lines is None:
            return None

        capturing = False
        capture: list[str] = []
        for line in lines:
            timestamp = line.get('_SOURCE_MONOTONIC_TIMESTAMP', '0')
            assert isinstance(timestamp, str)
            if int(timestamp) < start_usec - cls.TIMING_BUFFER:
                continue
            message = line.get('MESSAGE')
            if message is None:
                continue
            assert isinstance(message, str)
            if not capturing:
                for pattern in cls.JOURNAL_STARTS[type]:
                    if pattern.search(message):
                        capturing = True
                        break
            if capturing:
                capture.append(message)
                # Lack of an end expression indicates a one-line message
                if type not in cls.JOURNAL_ENDS:
                    capturing = False
                else:
                    for pattern in cls.JOURNAL_ENDS[type]:
                        if pattern.search(message):
                            capturing = False
                            break
                if not capturing:
                    cursor = line['__CURSOR']
                    break

        if cursor is not None:
            cls.data[f'{type}.cursor'] = cursor

        return capture


class TraceLine:
    class Column(enum.IntEnum):
        PID = 0
        CPU = 1
        BITS = 2
        TIMESTAMP = 3
        FUNCTION = 4

    def __init__(self, line: str):
        self.raw: Final[str] = line
        comm = line[:16]
        columns = line[17:].split()
        if len(columns) < 5 or line[16] != '-':
            raise ValueError('Invalid trace event', line)

        self.comm: Final[str] = comm.lstrip()
        self.pid: Final[int] = int(columns[self.Column.PID])
        self.cpu: Final[int] = int(columns[self.Column.CPU][1:-1])
        self.timestamp: Final[float] = float(columns[self.Column.TIMESTAMP].rstrip(':'))
        self.function: Final[str] = columns[self.Column.FUNCTION].rstrip(':')
        self.extra_args: Final[list[str]] = columns[self.Column.FUNCTION + 1:]


class TraceInterface(dbus.service.ServiceInterface):
    def __init__(self: Self):
        super().__init__(f'{DBUS_NAME}.Trace')

    @dbus.service.method()
    async def LogEvent(self, trace: 's', data: 'a{sv}'):  # type: ignore[valid-type,name-defined,no-untyped-def] # NOQA: F821, F722
        TraceHelper.logger.debug(f'Got trace event {trace} with additional data {data}')
        ts = time.time_ns()
        for k, v in data.items():
            if isinstance(v, dbus.Variant):
                data[k] = v.value
        event = await TraceHelper.prepare_event(trace, data)
        event.timestamp = ts / 1_000_000_000
        log = event.to_json()
        with open(f'{sls.pending}/{TraceHelper.name}/{ts}.json', 'w') as f:
            f.write(log)
