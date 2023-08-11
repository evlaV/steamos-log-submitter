# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import dbus_next as dbus
import inspect
import importlib.machinery
import json
import logging
import os
import psutil
import time
from collections.abc import Coroutine, Iterable
from dbus_next.constants import ErrorType
from typing import Any, Callable, Optional, Self

import steamos_log_submitter as sls
import steamos_log_submitter.dbus
import steamos_log_submitter.runner
import steamos_log_submitter.steam
import steamos_log_submitter.helpers as helpers
from steamos_log_submitter.types import JSONEncodable

__loader__: importlib.machinery.SourceFileLoader
config = sls.config.get_config(__loader__.name)
logger = logging.getLogger(__loader__.name)
socket = f'{sls.base}/steamos-log-submitter.socket'


class Serializable:
    _fields: list[str] = []

    def serialize(self) -> bytes:
        data = {}
        for field in self._fields:
            field_data = getattr(self, field)
            if field_data is not None:
                data[field] = field_data

        return json.dumps(data).encode() + b'\n'

    @classmethod
    def deserialize(cls, data: bytes) -> Optional[Self]:
        try:
            args = {}
            parsed_data = json.loads(data.decode())
            for field in cls._fields:
                field_data = parsed_data.get(field)
                if field_data is not None:
                    args[field] = field_data
            return cls(**args)
        except (json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError) as e:
            logger.warning('Failed to deserialize command', exc_info=e)
            return None


class Command(Serializable):
    _fields = ['command', 'args']

    def __init__(self, command: str, args: Optional[dict[str, Any]] = None):
        self.command = command
        self.args = args or {}


class Reply(Serializable):
    OK = 0
    UNKNOWN_ERROR = -1
    INVALID_COMMAND = -2
    INVALID_DATA = -3
    INVALID_ARGUMENTS = -4

    _fields = ['status', 'data']

    def __init__(self, status: int, data: Optional[JSONEncodable] = None):
        self.status = status
        self.data = data


class DaemonError(RuntimeError):
    def __init__(self, status: int, data: Optional[JSONEncodable] = None):
        if data:
            super().__init__(data)
        else:
            super().__init__()
        self.data = data
        self.status = status


class UnknownError(DaemonError):
    def __init__(self, data: Optional[JSONEncodable] = None):
        super().__init__(Reply.UNKNOWN_ERROR, data)


class InvalidCommandError(DaemonError):
    def __init__(self, data: Optional[JSONEncodable] = None):
        super().__init__(Reply.INVALID_COMMAND, data)


class InvalidDataError(DaemonError):
    def __init__(self, data: Optional[JSONEncodable] = None):
        super().__init__(Reply.INVALID_DATA, data)


class InvalidArgumentsError(DaemonError):
    def __init__(self, data: Optional[JSONEncodable] = None):
        super().__init__(Reply.INVALID_ARGUMENTS, data)


exception_map = {
    Reply.UNKNOWN_ERROR: UnknownError,
    Reply.INVALID_COMMAND: InvalidCommandError,
    Reply.INVALID_DATA: InvalidDataError,
    Reply.INVALID_ARGUMENTS: InvalidArgumentsError,
}


class Daemon:
    _startup = 20
    _interval = 3600

    def __init__(self, *, exit_on_shutdown: bool = False):
        self._conns: list[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = []
        self._exit_on_shutdown = exit_on_shutdown
        self._periodic_task: Optional[asyncio.Task[None]] = None
        self._serving = False
        self._suspend = 'inactive'
        self._trigger_active = False
        self._next_trigger = 0.0
        self._iface: Optional[DaemonInterface] = None

    async def _run_command(self, command: Command) -> Reply:
        if not command:
            logger.warning('Got invalid command data')
            return Reply(status=Reply.INVALID_DATA)
        function = self._commands.get(command.command)
        logger.info(f'Remote command {command.command} called')
        logger.debug(f'Arguments {command.args}')
        if not function:
            logger.warning(f'Unknown command {command.command} called')
            return Reply(status=Reply.INVALID_COMMAND)
        signature = inspect.signature(function)
        try:
            signature.bind(self, **command.args)
        except Exception as e:
            logger.error('Invocation does not match signature', exc_info=e)
            return Reply(status=Reply.INVALID_ARGUMENTS)
        try:
            return Reply(Reply.OK, await function(self, **command.args))
        except DaemonError as e:
            return Reply(e.status, data=e.data)
        except Exception as e:
            logger.error('Exception hit when attempting to run command', exc_info=e)
            return Reply(status=Reply.UNKNOWN_ERROR, data={'exception': str(e)})

    async def _trigger_periodic(self) -> None:
        next_interval = self._next_trigger - time.time()
        if next_interval > 0:
            logger.debug(f'Sleeping for {next_interval:.3f} seconds')
            await asyncio.sleep(next_interval)

        if not self._serving:
            return
        await self.trigger(wait=True)

    async def _conn_cb(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._conns.append((reader, writer))

        while self._serving:
            try:
                line = await reader.readline()
                if not line:
                    break
            except Exception as e:
                logger.error('Failed reading from remote connection', exc_info=e)
                continue
            try:
                command = Command.deserialize(line)
                if not command:
                    reply = Reply(Reply.INVALID_DATA)
                else:
                    reply = await self._run_command(command)
                writer.write(reply.serialize())
                await writer.drain()
            except Exception as e:
                logger.error('Failed executing remote connection', exc_info=e)
        self._conns.remove((reader, writer))

    def _setup_dbus(self) -> None:
        assert sls.dbus.system_bus
        self.iface = DaemonInterface(self)
        sls.dbus.system_bus.export('/com/valvesoftware/SteamOSLogSubmitter/Manager', self.iface)
        for helper in sls.helpers.list_helpers():
            try:
                helper_module = sls.helpers.create_helper(helper)
            except sls.exceptions.HelperError as e:
                logger.warning(f'Failed to enumerate helper {helper}', exc_info=e)
                continue
            if not helper_module.iface:
                continue
            camel_case = helper_module.__name__
            if not camel_case.endswith('Helper'):
                continue
            camel_case = camel_case[:-len('Helper')]
            sls.dbus.system_bus.export(f'/com/valvesoftware/SteamOSLogSubmitter/helpers/{camel_case}', helper_module.iface)

            for iface in helper_module.extra_ifaces.values():
                sls.dbus.system_bus.export(f'/com/valvesoftware/SteamOSLogSubmitter/helpers/{camel_case}', iface)
            for service, iface in helper_module.child_services.items():
                sls.dbus.system_bus.export(f'/com/valvesoftware/SteamOSLogSubmitter/helpers/{camel_case}/{service}', iface)

    async def _leave_suspend(self, iface: str, prop: str, value: str) -> None:
        if value == self._suspend:
            return
        self._suspend = value
        logger.debug(f'Suspend state changed to {value}')
        if value == 'inactive':
            if self._trigger_active:
                return
            logger.info('Woke up from suspend, attempting to submit logs')
            await asyncio.sleep(5)
            await self.trigger(wait=True)

    async def start(self) -> None:
        if self._serving:
            return
        logger.info('Daemon starting up')
        sls.config.upgrade()
        if os.access(socket, os.F_OK):
            os.unlink(socket)

        self._serving = True
        self._server = await asyncio.start_unix_server(self._conn_cb, path=socket)
        os.chmod(socket, 0o660)

        self._next_trigger = time.time() + self._startup
        last_trigger = config.get('last_trigger')
        if last_trigger is not None:
            next_trigger = float(last_trigger) + self._interval
            if next_trigger > self._next_trigger:
                self._next_trigger = next_trigger

        if not self.inhibited():
            self._periodic_task = asyncio.create_task(self._trigger_periodic())

        await sls.dbus.connect()
        assert sls.dbus.system_bus
        try:
            await sls.dbus.system_bus.request_name(sls.dbus.bus_name)
            self._setup_dbus()
        except dbus.errors.DBusError:
            logger.error('Failed to claim D-Bus bus name')

        suspend_target = sls.dbus.DBusObject('org.freedesktop.systemd1', '/org/freedesktop/systemd1/unit/suspend_2etarget')
        suspend_props = suspend_target.properties('org.freedesktop.systemd1.Unit')
        await suspend_props.subscribe('ActiveState', self._leave_suspend)

    async def shutdown(self) -> None:
        logger.info('Daemon shutting down')
        self._serving = False
        if self._periodic_task:
            self._periodic_task.cancel()
            try:
                await self._periodic_task
            except asyncio.CancelledError:
                pass
        self._server.close()
        await self._server.wait_closed()
        os.unlink(socket)

        if self._exit_on_shutdown:  # pragma: no cover
            loop = asyncio.get_event_loop()
            loop.stop()

    async def _trigger(self) -> None:
        if self.inhibited():
            return
        await sls.runner.trigger()
        last_trigger = time.time()
        config['last_trigger'] = last_trigger
        sls.config.write_config()
        self._next_trigger = last_trigger + self._interval
        if self._periodic_task:
            self._periodic_task.cancel()
            try:
                await self._periodic_task
            except asyncio.CancelledError:
                pass
        self._periodic_task = asyncio.create_task(self._trigger_periodic())

    async def trigger(self, wait: bool = True) -> None:
        if self.inhibited():
            return
        if self._trigger_active:
            return
        coro = self._trigger()
        if wait:
            self._trigger_active = True
            await coro
            self._trigger_active = False
        else:
            asyncio.create_task(coro)

    def enabled(self) -> bool:
        return sls.base_config.get('enable', 'off') == 'on'

    async def enable(self, state: bool) -> None:
        if not isinstance(state, bool):
            raise InvalidArgumentsError({'state': state})
        sls.base_config['enable'] = 'on' if state else 'off'
        sls.config.write_config()
        if self.iface:
            self.iface.emit_properties_changed({'Enabled': self.enabled()})

    async def enable_helpers(self, helpers: dict[str, bool]) -> None:
        _, invalid_helpers = sls.helpers.validate_helpers(helpers.keys())
        if invalid_helpers:
            raise InvalidArgumentsError({'invalid-helper': invalid_helpers})
        for helper, state in helpers.items():
            if not isinstance(state, bool):
                raise InvalidArgumentsError({'invalid-state': [helper, state]})
            logger.debug(f'Changing {helper} enable state to ' + ('on' if state else 'off'))
            sls.config.get_config(f'steamos_log_submitter.helpers.{helper}')['enable'] = 'on' if state else 'off'
        sls.config.write_config()

    async def inhibit(self, state: bool) -> None:
        if not isinstance(state, bool):
            return Reply(Reply.INVALID_ARGUMENTS, data={'state': state})
        sls.base_config['inhibit'] = 'on' if state else 'off'
        sls.config.write_config()
        if self.iface:
            self.iface.emit_properties_changed({'Inhibited': self.inhibited()})
        if state and self._periodic_task:
            self._periodic_task.cancel()
            try:
                await self._periodic_task
            except asyncio.CancelledError:
                pass
            self._periodic_task = None
        elif not state and not self._periodic_task:
            self._periodic_task = asyncio.create_task(self._trigger_periodic())

    def inhibited(self) -> bool:
        return sls.base_config.get('inhibit', 'off') == 'on'

    async def list_helpers(self) -> list[str]:
        return list(helpers.list_helpers())

    async def log_level(self, level: Optional[str] = None) -> dict[str, str]:
        if level is not None:
            if not sls.logging.valid_level(level):
                raise InvalidArgumentsError({'level': level})
            sls.config.migrate_key('logging', 'level')
            sls.logging.config['level'] = level.upper()
            sls.config.write_config()
            sls.logging.reconfigure_logging(sls.logging.config.get('path'))
        return {'level': sls.logging.config.get('level', 'WARNING').upper()}

    async def status(self) -> dict[str, JSONEncodable]:
        return {
            'enabled': self.enabled(),
            'inhibited': self.inhibited(),
        }

    async def helper_status(self, helpers: Optional[Iterable[str]] = None) -> dict[str, JSONEncodable]:
        if helpers is not None:
            _, invalid_helpers = sls.helpers.validate_helpers(helpers)
            if invalid_helpers:
                raise InvalidArgumentsError({'invalid-helper': list(invalid_helpers)})
        else:
            helpers = sls.helpers.list_helpers()
        status: dict[str, JSONEncodable] = {}
        for helper in (sls.helpers.create_helper(h) for h in helpers):
            status[helper.name] = {
                'enabled': helper.enabled(),
                'submission': helper.submit_enabled(),
                'collection': helper.collect_enabled(),
            }
        return status

    async def set_steam_info(self, key: str, value: str) -> None:
        if key not in (
            'deck_serial',
            'account_id',
            'account_name'
        ):
            logger.warning(f'Got Steam info change for invalid key {key}')
            raise InvalidArgumentsError({'key': key})

        logger.debug(f'Changing Steam info key {key} to {value}')
        sls.steam.config[key] = value
        sls.config.write_config()

    _commands: dict[str, Callable[..., Coroutine[Any, Any, JSONEncodable]]] = {
        'enable': enable,
        'enable-helpers': enable_helpers,
        'inhibit': inhibit,
        'status': status,
        'helper-status': helper_status,
        'list': list_helpers,
        'log-level': log_level,
        'set-steam-info': set_steam_info,
        'shutdown': shutdown,
        'trigger': trigger,
    }


class DaemonInterface(dbus.service.ServiceInterface):
    def __init__(self, daemon: 'sls.daemon.Daemon'):
        super().__init__(f'{sls.dbus.bus_name}.Manager')
        self.daemon = daemon

    @dbus.service.dbus_property()
    def Enabled(self) -> 'b':  # type: ignore # NOQA: F821
        return self.daemon.enabled()

    @Enabled.setter
    async def set_enabled(self, enable: 'b'):  # type: ignore # NOQA: F821
        await self.daemon.enable(enable)

    @dbus.service.dbus_property()
    def Inhibited(self) -> 'b':  # type: ignore # NOQA: F821
        return self.daemon.inhibited()

    @Inhibited.setter
    async def set_inhibited(self, inhibit: 'b'):  # type: ignore # NOQA: F821
        await self.daemon.inhibit(inhibit)

    @dbus.service.method()
    async def Trigger(self):  # type: ignore
        await self.daemon.trigger()

    @dbus.service.method()
    async def Shutdown(self):  # type: ignore
        await self.daemon.shutdown()

    @dbus.service.method()
    async def SetSteamInfo(self, key: 's', value: 's'):  # type: ignore # NOQA: F821
        try:
            await self.daemon.set_steam_info(key, value)
        except InvalidArgumentsError as e:
            raise dbus.errors.DBusError(ErrorType.INVALID_ARGS, f'Invalid argument {e.data}')


if __name__ == '__main__':  # pragma: no cover
    sls.logging.reconfigure_logging(sls.logging.config.get('path'))
    try:
        os.nice(10)  # De-prioritize background work
        psutil.Process().ionice(psutil.IOPRIO_CLASS_BE, value=7)
    except OSError as e:
        logger.error('Failed to downgrade process priority', exc_info=e)
    daemon = Daemon(exit_on_shutdown=True)
    loop = asyncio.get_event_loop()
    loop.create_task(daemon.start())
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        if os.access(socket, os.F_OK):
            os.unlink(socket)
