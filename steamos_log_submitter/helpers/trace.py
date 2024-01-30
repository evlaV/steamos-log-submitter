# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next as dbus
from typing import Self

import steamos_log_submitter as sls
from steamos_log_submitter.constants import DBUS_NAME

from . import Helper, HelperResult


class TraceHelper(Helper):
    @classmethod
    def _setup(cls) -> None:
        super()._setup()
        cls.extra_ifaces.append(TraceInterface())

    @classmethod
    async def collect(cls) -> list[str]:
        await sls.util.read_journal('kernel')
        return []

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        return HelperResult(HelperResult.PERMANENT_ERROR)


class TraceInterface(dbus.service.ServiceInterface):
    def __init__(self: Self):
        super().__init__(f'{DBUS_NAME}.Trace')

    @dbus.service.method()
    async def LogEvent(self, trace: 'as', data: 'a{sv}'):  # type: ignore[valid-type,no-untyped-def] # NOQA: F821, F722
        pass
