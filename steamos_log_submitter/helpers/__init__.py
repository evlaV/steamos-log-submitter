# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import importlib
import pkgutil
import steamos_log_submitter as sls
import steamos_log_submitter.lockfile as lockfile


class HelperError(RuntimeError):
    pass


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
