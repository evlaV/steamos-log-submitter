# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import abc
import dbus_next as dbus
import enum
import importlib
import logging
import os
import pkgutil
import shutil
import sys
import tempfile
import typing
from collections.abc import Container, Iterable
from types import TracebackType
from typing import Any, ClassVar, Optional, Type

import steamos_log_submitter as sls
import steamos_log_submitter.dbus
import steamos_log_submitter.lockfile
from steamos_log_submitter.constants import DBUS_NAME
from steamos_log_submitter.daemon import DaemonInterface
from steamos_log_submitter.types import JSONEncodable

logger = logging.getLogger(__name__)


class HelperResult(enum.Enum):
    OK = 0
    TRANSIENT_ERROR = -1
    PERMANENT_ERROR = -2
    CLASS_ERROR = -3

    @staticmethod
    def check(result: bool, *, true_code: int = OK, false_code: int = TRANSIENT_ERROR) -> 'HelperResult':
        if result:
            return HelperResult(true_code)
        return HelperResult(false_code)


class HelperInterface(dbus.service.ServiceInterface):
    def __init__(self, helper: Type['Helper']):
        super().__init__(f'{DBUS_NAME}.Helper')
        self.helper = helper
        self.daemon: Optional[DaemonInterface] = None

    @dbus.service.dbus_property()
    def Enabled(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return self.helper.enabled()

    @Enabled.setter
    def set_enabled(self, enable: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        return self.helper.enable(enable)

    @dbus.service.dbus_property()
    def CollectEnabled(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return self.helper.collect_enabled()

    @CollectEnabled.setter
    def set_collect_enabled(self, enable: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        return self.helper.enable_collect(enable)

    @dbus.service.dbus_property()
    def SubmitEnabled(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return self.helper.submit_enabled()

    @SubmitEnabled.setter
    def set_submit_enabled(self, enable: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        return self.helper.enable_submit(enable)

    @dbus.service.method()
    async def Collect(self) -> 'as':  # type: ignore[valid-type] # NOQA: F821, F722
        return await self.helper.collect()

    @dbus.service.method()
    def ListFailed(self) -> 'as':  # type: ignore[valid-type] # NOQA: F821, F722
        return list(self.helper.list_failed())

    @dbus.service.method()
    def ListPending(self) -> 'as':  # type: ignore[valid-type] # NOQA: F821, F722
        return list(self.helper.list_pending())

    @dbus.service.method()
    def ListUploaded(self) -> 'as':  # type: ignore[valid-type] # NOQA: F821, F722
        return list(self.helper.list_uploaded())

    @dbus.service.signal()
    def NewLogs(self, logs: list[str]) -> 'as':  # type: ignore[valid-type] # NOQA: F821, F722
        pending = set(self.helper.list_pending())
        logs = [log for log in logs if log in pending]
        if self.daemon:
            self.daemon.NewLogs([f'{self.helper.name}/{log}' for log in logs])
        return logs

    @dbus.service.dbus_property(access=dbus.constants.PropertyAccess.READ)
    def LastCollected(self) -> 'x':  # type: ignore[name-defined] # NOQA: F821
        timestamp = self.helper.config.get('newest')
        if timestamp is None:
            return 0
        return int(float(timestamp))


class Helper(abc.ABC):
    defaults: ClassVar[Optional[dict[str, JSONEncodable]]] = None
    valid_extensions: ClassVar[Container[str]] = frozenset()

    __name__: str
    name: str
    config: sls.config.ConfigSection
    data: sls.data.DataStore
    iface: Optional[HelperInterface]
    extra_ifaces: list[dbus.service.ServiceInterface]
    child_services: dict[str, dbus.service.ServiceInterface]
    logger: logging.Logger

    @classmethod
    def __init_subclass__(cls) -> None:
        module = cls.__module__
        cls.logger = logging.getLogger(module)
        cls.iface = None
        cls.extra_ifaces = []
        cls.child_services = {}
        if module == __name__:
            return
        sys.modules[module].helper = cls  # type: ignore[attr-defined]

    @classmethod
    def _setup(cls) -> None:
        module = cls.__module__
        if module == __name__:
            return
        cls.extra_ifaces = []
        cls.child_services = {}
        cls.name = module.split('.', 2)[2]
        cls.config = sls.config.get_config(module)
        cls.data = sls.data.get_data(module, defaults=cls.defaults)
        cls.iface = HelperInterface(cls)

    @classmethod
    async def collect(cls) -> list[str]:
        last_collected: Optional[float] = None
        newest: Optional[float] = None
        newer: list[str] = []
        newest_updated = False
        try:
            if 'newest' in cls.config:
                last_collected = round(float(cls.config['newest']), 3)
        except ValueError:
            pass

        for log in cls.list_pending():
            try:
                stat = os.stat(f'{sls.pending}/{cls.name}/{log}')
            except OSError:
                cls.logger.warning(f'Failed to stat {log}, ignoring')
                continue
            mtime = round(stat.st_mtime, 3)
            if last_collected is None or mtime > last_collected:
                newer.append(log)
            if newest is None or mtime > newest:
                newest = mtime
        if newest is not None and (last_collected is None or newest > last_collected):
            cls.config['newest'] = newest
            newest_updated = True
        if newer and cls.iface:
            cls.iface.NewLogs(newer)
        if newest_updated:
            sls.config.write_config()
            if cls.iface:
                assert newest is not None
                cls.iface.emit_properties_changed({'LastCollected': int(newest)})
        return newer

    @classmethod
    @abc.abstractmethod
    async def submit(cls, fname: str) -> HelperResult:
        raise NotImplementedError

    @classmethod
    def enabled(cls) -> bool:
        return cls.config.get('enable', 'on') == 'on'

    @classmethod
    def enable(cls, enabled: bool, /) -> None:
        cls.config['enable'] = 'on' if enabled else 'off'
        sls.config.write_config()
        if cls.iface:
            cls.iface.emit_properties_changed({'Enabled': enabled})

    @classmethod
    def collect_enabled(cls) -> bool:
        return cls.config.get('collect', 'on') == 'on'

    @classmethod
    def enable_collect(cls, enabled: bool, /) -> None:
        cls.config['collect'] = 'on' if enabled else 'off'
        sls.config.write_config()
        if cls.iface:
            cls.iface.emit_properties_changed({'CollectEnabled': enabled})

    @classmethod
    def submit_enabled(cls) -> bool:
        return cls.config.get('submit', 'on') == 'on'

    @classmethod
    def enable_submit(cls, enabled: bool, /) -> None:
        cls.config['submit'] = 'on' if enabled else 'off'
        sls.config.write_config()
        if cls.iface:
            cls.iface.emit_properties_changed({'SubmitEnabled': enabled})

    @classmethod
    def lock(cls) -> sls.lockfile.Lockfile:
        return sls.lockfile.Lockfile(f'{sls.pending}/{cls.name}/.lock')

    @classmethod
    def filter_log(cls, fname: str) -> bool:
        if fname.startswith('.'):
            return False
        _, ext = os.path.splitext(os.path.basename(fname))
        if cls.valid_extensions and ext not in cls.valid_extensions:
            return False
        return True

    @classmethod
    def list_failed(cls) -> Iterable[str]:
        return cls.list_type(sls.failed)

    @classmethod
    def list_pending(cls) -> Iterable[str]:
        return cls.list_type(sls.pending)

    @classmethod
    def list_uploaded(cls) -> Iterable[str]:
        return cls.list_type(sls.uploaded)

    @classmethod
    def list_type(cls, base: str) -> Iterable[str]:
        try:
            return (log for log in os.listdir(f'{base}/{cls.name}') if cls.filter_log(log) and os.access(f'{base}/{cls.name}/{log}', os.R_OK))
        except OSError as e:
            cls.logger.error(f'Encountered error listing logs for {cls.name}: {e}')
            return ()


def create_helper(category: str) -> Optional[Helper]:
    try:
        helper = importlib.import_module(f'steamos_log_submitter.helpers.{category}')
    except ModuleNotFoundError:
        logger.error(f'Helper module {category} not found')
        return None
    if not hasattr(helper, 'helper'):
        logger.error(f'Helper module {category} does not contain helper class')
        return None
    helper.helper._setup()
    assert issubclass(helper.helper, Helper)
    return typing.cast(Helper, helper.helper)


def list_helpers() -> Iterable[str]:
    return (helper.name for helper in pkgutil.iter_modules(__path__))


def validate_helpers(helpers: Iterable[str]) -> tuple[list[str], list[str]]:
    all_helpers = set(list_helpers())
    requested_helpers = set(helpers)
    invalid_helpers = requested_helpers - all_helpers
    valid_helpers = requested_helpers & all_helpers
    return sorted(valid_helpers), sorted(invalid_helpers)


class StagingFile:
    def __init__(self, category: str, name: str, mode: str = 'w+b'):
        self._final_name = f'{sls.pending}/{category}/{name}'
        self._tempfile = tempfile.NamedTemporaryFile(mode=mode, dir=f'{sls.pending}/{category}', prefix='.staging-', delete=False)

    def close(self) -> None:
        self._tempfile.close()
        if os.geteuid() == 0:
            shutil.chown(self.name, user='steamos-log-submitter')
        os.rename(self.name, self._final_name)

    def __getattr__(self, attr: str) -> Any:  # type: ignore[misc]
        return getattr(self._tempfile, attr)

    def __enter__(self) -> 'StagingFile':
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> bool:
        self.close()
        return not exc_type


class TransientError(dbus.errors.DBusError):
    def __init__(self, text: Optional[str] = None):
        text = text or 'A transient error occurred'
        super().__init__(f'{DBUS_NAME}.Error.TransientError', text)


class PermanentError(dbus.errors.DBusError):
    def __init__(self, text: Optional[str] = None):
        text = text or 'A permanent error occurred'
        super().__init__(f'{DBUS_NAME}.Error.PermanentError', text)


class ClassError(dbus.errors.DBusError):
    def __init__(self, text: Optional[str] = None):
        text = text or 'A classwide error occurred'
        super().__init__(f'{DBUS_NAME}.Error.ClassError', text)


def raise_dbus_error(result: HelperResult) -> None:
    if result == HelperResult.OK:
        return
    if result == HelperResult.TRANSIENT_ERROR:
        raise TransientError()
    if result == HelperResult.PERMANENT_ERROR:
        raise PermanentError()
    if result == HelperResult.CLASS_ERROR:
        raise ClassError()
    else:  # pragma: no cover
        assert False, 'Unknown error type'
