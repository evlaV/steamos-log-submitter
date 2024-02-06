# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next as dbus
import enum
import json
import time
from typing import Final, Optional, Self

import steamos_log_submitter as sls
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

    def to_json(self) -> str:
        data: dict[str, JSONEncodable] = {
            'type': self.type
        }
        if self.timestamp:
            data['timestamp'] = self.timestamp
        if self.uptime:
            data['uptime'] = self.uptime
        if self.pid is not None:
            data['pid'] = self.pid
        if self.appid is not None:
            data['appid'] = self.appid
        return json.dumps(data)


class TraceHelper(Helper):
    @classmethod
    def _setup(cls) -> None:
        super()._setup()
        cls.extra_ifaces.append(TraceInterface())

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        return HelperResult.PERMANENT_ERROR

    @classmethod
    def prepare_event(cls, line: str, data: dict[str, DBusEncodable]) -> TraceEvent:
        trace = TraceLine(line)

        event = None
        if trace.function == 'mark_victim':
            if not trace.extra_args:
                raise ValueError('Invalid OOM event missing victim pid')
            if not trace.extra_args[0].startswith('pid='):
                raise ValueError(f'Invalid pid in {trace.extra_args[0]}')

            event = TraceEvent(TraceEvent.Type.OOM)
            event.pid = int(trace.extra_args[0].split('=', 1)[1])

        if event is None:
            raise ValueError

        event.timestamp = time.time()
        event.uptime = trace.timestamp
        if event.pid is None:
            event.pid = trace.pid

        if 'appid' in data:
            if not isinstance(data['appid'], int):
                raise ValueError
            event.appid = data['appid']

        if event.appid is None and event.pid is not None:
            event.appid = sls.util.get_appid(event.pid)

        return event

    @classmethod
    async def read_journal(cls, type: TraceEvent.Type) -> Optional[list[dict[str, JSONEncodable]]]:
        pass


class TraceLine:
    class Column(enum.IntEnum):
        PID = 0
        CPU = 1
        BITS = 2
        TIMESTAMP = 3
        FUNCTION = 4

    def __init__(self, line: str):
        self.raw: Final[str] = line
        task = line[:16]
        columns = line[17:].split()
        if len(columns) < 5 or line[16] != '-':
            raise ValueError('Invalid trace event', line)

        self.task: Final[str] = task.lstrip()
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
        event = TraceHelper.prepare_event(trace, data)
        event.to_json()
