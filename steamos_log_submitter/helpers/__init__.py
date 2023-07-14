# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import importlib
import logging
import os
import pkgutil
import sys
import tempfile
import steamos_log_submitter as sls
import steamos_log_submitter.sentry
import steamos_log_submitter.lockfile
from steamos_log_submitter.exceptions import HelperError


class HelperResult:
    OK = 0
    TRANSIENT_ERROR = -1
    PERMANENT_ERROR = -2
    CLASS_ERROR = -3

    def __init__(self, code=OK):
        super(HelperResult, self).__init__()
        self.code = code

    @staticmethod
    def check(result, *, true_code=OK, false_code=TRANSIENT_ERROR):
        if result:
            return HelperResult(true_code)
        return HelperResult(false_code)


class MetaHelper(type):
    def __new__(cls, name, bases, dct):
        newcls = super().__new__(cls, name, bases, dct)
        newcls.config = sls.get_config(newcls.__module__)
        newcls.data = sls.get_data(newcls.__module__, defaults=dct.get('defaults'))
        newcls.logger = logging.getLogger(newcls.__module__)
        sys.modules[newcls.__module__].helper = newcls
        return newcls


class Helper(metaclass=MetaHelper):
    @classmethod
    async def collect(cls) -> bool:
        return False

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        raise NotImplementedError


class SentryHelper(Helper):
    @classmethod
    async def send_event(cls, **kwargs):
        ok = await sls.sentry.send_event(cls.config['dsn'], **kwargs)
        return HelperResult.check(ok)


def create_helper(category):
    try:
        helper = importlib.import_module(f'steamos_log_submitter.helpers.{category}')
        if not hasattr(helper, 'helper'):
            raise HelperError('Helper module does not contain submit function')
    except ModuleNotFoundError as e:
        raise HelperError from e
    return helper.helper


def list_helpers():
    return [helper.name for helper in pkgutil.iter_modules(__path__)]


def lock(helper):
    return sls.lockfile.Lockfile(f'{sls.pending}/{helper}/.lock')


class StagingFile:
    def __init__(self, category, name, mode='w+b'):
        self._final_name = f'{sls.pending}/{category}/{name}'
        self._tempfile = tempfile.NamedTemporaryFile(mode=mode, dir=f'{sls.pending}/{category}', prefix='.staging-', delete=False)

    def close(self):
        self._tempfile.close()
        os.rename(self.name, self._final_name)

    def __getattr__(self, attr):
        return getattr(self._tempfile, attr)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return not exc_type
