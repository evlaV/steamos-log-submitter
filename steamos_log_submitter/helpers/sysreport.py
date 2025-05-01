# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next as dbus
import logging
import os
import random
import shutil
from . import Helper, HelperResult

import steamos_log_submitter as sls
from steamos_log_submitter.aggregators.sentry import SentryEvent
from steamos_log_submitter.constants import DBUS_NAME
from steamos_log_submitter.types import JSONEncodable

logger = logging.getLogger(__name__)


class SysreportHelper(Helper):
    valid_extensions = frozenset({'.zip'})
    alphabet = '34679ABEHJKLMNPSTUWXYZ'

    @classmethod
    def _setup(cls) -> bool:
        if not super()._setup():
            return False
        cls.extra_ifaces.append(SysreportInterface())
        return True

    @classmethod
    def make_id(cls) -> str:
        id = random.choices(cls.alphabet, k=8)
        return ''.join(id[:4]) + '-' + ''.join(id[4:])

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        id, _ = os.path.splitext(os.path.basename(fname))

        tags: dict[str, JSONEncodable] = {
            'friendly_id': id
        }

        try:
            with open(fname, 'rb') as f:
                attachment = f.read()
        except OSError:
            return HelperResult.TRANSIENT_ERROR

        event = SentryEvent(cls.config['dsn'])
        event.add_attachment({
            'mime-type': 'application/zip',
            'filename': 'report.zip',
            'data': attachment
        })
        event.tags = tags
        event.message = f'System report {id}'
        return HelperResult.check(await event.send())

    @classmethod
    async def send_report(cls, path: str) -> str | HelperResult:
        if not path.endswith('.zip'):
            return HelperResult.PERMANENT_ERROR

        id = cls.make_id()
        name = f'{id}.zip'
        new_path = f'{sls.pending}/{cls.name}/{name}'
        shutil.copyfile(path, new_path)

        result = (await sls.runner.submit_category(cls, [name]))[name]
        if isinstance(result, HelperResult) and result == HelperResult.OK:
            return id
        try:
            os.replace(new_path, f'{sls.failed}/{cls.name}/{id}.zip')
        except OSError:
            pass

        if isinstance(result, Exception):
            raise result
        return result


class SysreportInterface(dbus.service.ServiceInterface):
    def __init__(self) -> None:
        super().__init__(f'{DBUS_NAME}.Sysreport')

    @dbus.service.method()
    async def SendReport(self, path: 's') -> 's':  # type: ignore[name-defined] # NOQA: F821
        try:
            result = await SysreportHelper.send_report(path)
        except FileNotFoundError as e:
            raise dbus.errors.DBusError('org.freedesktop.DBus.Error.FileNotFound',
                                        f'{e.strerror}: {e.filename}') from e
        except Exception as e:
            raise dbus.errors.DBusError('org.freedesktop.DBus.Error.Failed',
                                        f'{type(e).__name__}: {str(e)}') from e
        if isinstance(result, str):
            return result
        sls.helpers.raise_dbus_error(result)
