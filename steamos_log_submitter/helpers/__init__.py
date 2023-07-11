# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import importlib
import os
import pkgutil
import tempfile
import steamos_log_submitter as sls
import steamos_log_submitter.lockfile as lockfile


class HelperError(NotImplementedError):
    pass


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


def create_helper(category):
    try:
        helper = importlib.import_module(f'steamos_log_submitter.helpers.{category}')
        if not hasattr(helper, 'submit'):
            raise HelperError('Helper module does not contain submit function')
    except ModuleNotFoundError as e:
        raise HelperError from e
    return helper


def list_helpers():
    return [helper.name for helper in pkgutil.iter_modules(__path__)]


def lock(helper):
    return lockfile.Lockfile(f'{sls.pending}/{helper}/.lock')


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
