# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next
import importlib
import logging
import os
import pkgutil
import sys
import tempfile
from collections.abc import Iterable
from types import TracebackType
from typing import Any, Optional, Type
import steamos_log_submitter as sls
import steamos_log_submitter.sentry
import steamos_log_submitter.lockfile
from steamos_log_submitter.exceptions import HelperError
from steamos_log_submitter.types import JSONEncodable


class HelperResult:
    OK = 0
    TRANSIENT_ERROR = -1
    PERMANENT_ERROR = -2
    CLASS_ERROR = -3

    def __init__(self, code: int = OK):
        super(HelperResult, self).__init__()
        self.code = code

    @staticmethod
    def check(result: bool, *, true_code: int = OK, false_code: int = TRANSIENT_ERROR) -> 'HelperResult':
        if result:
            return HelperResult(true_code)
        return HelperResult(false_code)


class HelperInterface(dbus_next.service.ServiceInterface):
    def __init__(self, helper: Type['Helper']):
        super().__init__(f'{sls.dbus.bus_name}.Helper')
        self.helper = helper

    @dbus_next.service.dbus_property()
    def Enabled(self) -> 'b':  # type: ignore # NOQA: F821
        return self.helper.enabled()

    @Enabled.setter
    def set_enabled(self, enable: 'b'):  # type: ignore # NOQA: F821
        return self.helper.enable(enable)

    @dbus_next.service.dbus_property()
    def CollectEnabled(self) -> 'b':  # type: ignore # NOQA: F821
        return self.helper.collect_enabled()

    @CollectEnabled.setter
    def set_collect_enabled(self, enable: 'b'):  # type: ignore # NOQA: F821
        return self.helper.enable_collect(enable)

    @dbus_next.service.dbus_property()
    def SubmitEnabled(self) -> 'b':  # type: ignore # NOQA: F821
        return self.helper.submit_enabled()

    @SubmitEnabled.setter
    def set_submit_enabled(self, enable: 'b'):  # type: ignore # NOQA: F821
        return self.helper.enable_submit(enable)


class Helper:
    defaults: Optional[dict[str, JSONEncodable]] = None

    __name__: str
    name: str
    config: sls.config.ConfigSection
    data: sls.data.DataStore
    iface: Optional[HelperInterface]
    logger: logging.Logger

    @classmethod
    def __init_subclass__(cls) -> None:
        module = cls.__module__
        cls.logger = logging.getLogger(module)
        cls.iface = None
        if module == __name__:
            return
        sys.modules[module].helper = cls  # type: ignore

    @classmethod
    def _setup(cls) -> None:
        module = cls.__module__
        if module == __name__:
            return
        cls.name = module.split('.', 2)[2]
        cls.config = sls.config.get_config(module)
        cls.data = sls.data.get_data(module, defaults=cls.defaults)
        cls.iface = HelperInterface(cls)

    @classmethod
    async def collect(cls) -> bool:
        return False

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        raise NotImplementedError

    @classmethod
    def enabled(cls) -> bool:
        return cls.config.get('enable', 'on') == 'on'

    @classmethod
    def enable(cls, enabled: bool, /) -> None:
        cls.config['enable'] = 'on' if enabled else 'off'
        if cls.iface:
            cls.iface.emit_properties_changed({'Enabled': enabled})

    @classmethod
    def collect_enabled(cls) -> bool:
        return cls.config.get('collect', 'on') == 'on'

    @classmethod
    def enable_collect(cls, enabled: bool, /) -> None:
        cls.config['collect'] = 'on' if enabled else 'off'
        if cls.iface:
            cls.iface.emit_properties_changed({'CollectEnabled': enabled})

    @classmethod
    def submit_enabled(cls) -> bool:
        return cls.config.get('submit', 'on') == 'on'

    @classmethod
    def enable_submit(cls, enabled: bool, /) -> None:
        cls.config['submit'] = 'on' if enabled else 'off'
        if cls.iface:
            cls.iface.emit_properties_changed({'SubmitEnabled': enabled})

    @classmethod
    def lock(cls) -> sls.lockfile.Lockfile:
        return sls.lockfile.Lockfile(f'{sls.pending}/{cls.name}/.lock')


class SentryHelper(Helper):
    @classmethod
    async def send_event(cls, **kwargs: Any) -> HelperResult:
        ok = await sls.sentry.send_event(cls.config['dsn'], **kwargs)
        return HelperResult.check(ok)


def create_helper(category: str) -> Helper:
    try:
        helper = importlib.import_module(f'steamos_log_submitter.helpers.{category}')
        if not hasattr(helper, 'helper'):
            raise HelperError('Helper module does not contain submit function')
        helper.helper._setup()
    except ModuleNotFoundError as e:
        raise HelperError from e
    return helper.helper


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
        os.rename(self.name, self._final_name)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._tempfile, attr)

    def __enter__(self) -> 'StagingFile':
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> bool:
        self.close()
        return not exc_type
