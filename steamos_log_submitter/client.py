# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next as dbus
import json
import logging
from collections.abc import Callable, Iterable
from typing import Any, NoReturn, Optional, Self

import steamos_log_submitter as sls
import steamos_log_submitter.daemon as daemon
import steamos_log_submitter.dbus
from steamos_log_submitter.types import JSON

logger = logging.getLogger(__name__)


class Client:
    def __init__(self, *, bus: str = 'com.valvesoftware.SteamOSLogSubmitter'):
        self._bus = bus
        self._manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
        self._properties = self._manager.properties('com.valvesoftware.SteamOSLogSubmitter.Manager')
        self._iface: Optional[sls.dbus.DBusInterface] = None

    async def _connect(self) -> None:
        if not self._iface:
            self._iface = await self._manager.interface('com.valvesoftware.SteamOSLogSubmitter.Manager')

    @staticmethod
    def _rethrow(exc: BaseException) -> NoReturn:
        if isinstance(exc, dbus.errors.DBusError):
            if exc.type in daemon.DaemonError.map:
                new_exc = daemon.DaemonError.map[exc.type]
                raise new_exc(json.loads(exc.text)) from exc
            raise daemon.UnknownError({'text': exc.text}) from exc
        raise exc

    @staticmethod
    def command(fn: Callable) -> Callable:
        async def wrapped(self: Self, *args: Any, **kwargs: Any) -> Any:
            await self._connect()
            try:
                return await fn(self, *args, **kwargs)
            except Exception as e:
                self._rethrow(e)

        return wrapped

    async def validate_helpers(self, requested_helpers: Iterable[str]) -> tuple[list[str], list[str]]:
        valid_names = set(await self.list())
        requested_names = set(requested_helpers)
        return sorted(valid_names & requested_names), sorted(requested_names - valid_names)

    @command
    async def enable(self, state: bool = True) -> None:
        await self._properties.set('Enabled', state)

    async def disable(self) -> None:
        await self.enable(False)

    async def enable_helpers(self, helpers: list[str]) -> None:
        await self.set_helpers_enabled({helper: True for helper in helpers})

    async def disable_helpers(self, helpers: list[str]) -> None:
        await self.set_helpers_enabled({helper: False for helper in helpers})

    @command
    async def set_helpers_enabled(self, helpers: dict[str, bool]) -> None:
        valid_helpers, invalid_helpers = await self.validate_helpers(helpers.keys())
        if invalid_helpers:
            raise daemon.InvalidArgumentsError({'invalid-helper': list(invalid_helpers)})
        for helper in valid_helpers:
            camel_case = sls.util.camel_case(helper)
            dbus_object = sls.dbus.DBusObject(self._bus, f'/com/valvesoftware/SteamOSLogSubmitter/helpers/{camel_case}')
            props = dbus_object.properties('com.valvesoftware.SteamOSLogSubmitter.Helper')
            await props.set('Enabled', helpers[helper])

    @command
    async def status(self) -> bool:
        return await self._properties['Enabled']

    @command
    async def helper_status(self, helpers: Optional[list[str]] = None) -> dict[str, dict[str, JSON]]:
        if not helpers:
            helpers = await self.list()
        else:
            helpers, invalid_helpers = await self.validate_helpers(helpers)
            if invalid_helpers:
                raise daemon.InvalidArgumentsError({'invalid-helper': list(invalid_helpers)})
        status = {}
        assert helpers is not None  # mypy bug: both branches set helpers to be not None, but mypy can't deduce that
        for helper in helpers:
            camel_case = sls.util.camel_case(helper)
            dbus_object = sls.dbus.DBusObject(self._bus, f'/com/valvesoftware/SteamOSLogSubmitter/helpers/{camel_case}')
            props = dbus_object.properties('com.valvesoftware.SteamOSLogSubmitter.Helper')
            status[helper] = {
                'enabled': await props['Enabled'],
                'collection': await props['CollectEnabled'],
                'submission': await props['SubmitEnabled'],
            }
        return status

    @command
    async def list(self) -> list[str]:
        helpers = sls.dbus.DBusObject(self._bus, '/com/valvesoftware/SteamOSLogSubmitter/helpers')
        return [sls.util.snake_case(child.rsplit('/')[-1]) for child in await helpers.list_children()]

    @command
    async def log_level(self) -> str:
        return await self._properties['LogLevel']

    @command
    async def set_log_level(self, level: str) -> None:
        return await self._properties.set('LogLevel', level)

    @command
    async def set_steam_info(self, key: str, value: Any) -> None:
        assert self._iface
        await self._iface.set_steam_info(key, str(value))

    @command
    async def shutdown(self) -> None:
        assert self._iface
        await self._iface.shutdown()

    @command
    async def trigger(self, wait: bool = True) -> None:
        assert self._iface
        if wait:
            await self._iface.trigger()
        else:
            await self._iface.trigger_async()
