# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next as dbus
import pytest
import os
import tempfile
import steamos_log_submitter as sls
import steamos_log_submitter.aggregators.sentry as sentry
from steamos_log_submitter.helpers import HelperResult
from steamos_log_submitter.helpers.sysreport import SysreportHelper as helper
from .. import awaitable, always_raise, custom_dsn, setup_categories
from .. import helper_directory, mock_config, patch_module  # NOQA: F401
from ..daemon import dbus_daemon
from ..dbus import mock_dbus, MockDBusObject  # NOQA: F401

dsn = custom_dsn('helpers.sysreport')


def test_id_format(monkeypatch):
    monkeypatch.setattr(helper, 'alphabet', 'X')
    assert helper.make_id() == 'XXXX-XXXX'


@pytest.mark.asyncio
async def test_send_failures(helper_directory):
    assert await helper.send_report('report.tar.gz') == HelperResult.PERMANENT_ERROR
    try:
        await helper.send_report('/does/not/exist.zip')
        assert False
    except FileNotFoundError:
        pass


@pytest.mark.asyncio
async def test_move_failed(helper_directory, monkeypatch):
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'alphabet', 'X')
    monkeypatch.setattr(helper, 'submit', awaitable(lambda _: HelperResult.TRANSIENT_ERROR))
    setup_categories(['sysreport'])

    zip = tempfile.NamedTemporaryFile(suffix='.zip')
    assert await helper.send_report(zip.name) == HelperResult.TRANSIENT_ERROR
    assert not os.access(f'{sls.pending}/{helper.name}/XXXX-XXXX.zip', os.F_OK)
    assert os.access(f'{sls.failed}/{helper.name}/XXXX-XXXX.zip', os.F_OK)


@pytest.mark.asyncio
async def test_submit_missing_file(monkeypatch):
    daemon, bus = await dbus_daemon(monkeypatch)
    usb = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Sysreport')
    iface = await usb.interface(f'{sls.constants.DBUS_NAME}.Sysreport')
    try:
        await iface.send_report('/does/not/exist.zip')
        assert False
    except dbus.errors.DBusError as e:
        assert e.type == 'org.freedesktop.DBus.Error.FileNotFound'

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_transient_error(helper_directory, monkeypatch):
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'alphabet', 'X')
    monkeypatch.setattr(helper, 'submit', awaitable(lambda _: HelperResult.TRANSIENT_ERROR))
    setup_categories(['sysreport'])

    zip = tempfile.NamedTemporaryFile(suffix='.zip')

    daemon, bus = await dbus_daemon(monkeypatch)
    usb = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Sysreport')
    iface = await usb.interface(f'{sls.constants.DBUS_NAME}.Sysreport')

    try:
        await iface.send_report(zip.name)
        assert False
    except dbus.errors.DBusError as e:
        assert e.type == f'{sls.constants.DBUS_NAME}.Error.TransientError'

    assert not os.access(f'{sls.pending}/{helper.name}/XXXX-XXXX.zip', os.F_OK)
    assert os.access(f'{sls.failed}/{helper.name}/XXXX-XXXX.zip', os.F_OK)


@pytest.mark.asyncio
async def test_permanent_error(helper_directory, monkeypatch):
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'alphabet', 'X')
    monkeypatch.setattr(helper, 'submit', awaitable(lambda _: HelperResult.PERMANENT_ERROR))
    setup_categories(['sysreport'])

    zip = tempfile.NamedTemporaryFile(suffix='.zip')

    daemon, bus = await dbus_daemon(monkeypatch)
    usb = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Sysreport')
    iface = await usb.interface(f'{sls.constants.DBUS_NAME}.Sysreport')

    try:
        await iface.send_report(zip.name)
        assert False
    except dbus.errors.DBusError as e:
        assert e.type == f'{sls.constants.DBUS_NAME}.Error.PermanentError'

    assert not os.access(f'{sls.pending}/{helper.name}/XXXX-XXXX.zip', os.F_OK)
    assert os.access(f'{sls.failed}/{helper.name}/XXXX-XXXX.zip', os.F_OK)


@pytest.mark.asyncio
async def test_other_error(helper_directory, monkeypatch):
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'alphabet', 'X')
    monkeypatch.setattr(helper, 'submit', awaitable(always_raise(RuntimeError())))
    setup_categories(['sysreport'])

    zip = tempfile.NamedTemporaryFile(suffix='.zip')

    daemon, bus = await dbus_daemon(monkeypatch)
    usb = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Sysreport')
    iface = await usb.interface(f'{sls.constants.DBUS_NAME}.Sysreport')

    try:
        await iface.send_report(zip.name)
        assert False
    except dbus.errors.DBusError as e:
        assert e.type == 'org.freedesktop.DBus.Error.Failed'

    assert not os.access(f'{sls.pending}/{helper.name}/XXXX-XXXX.zip', os.F_OK)
    assert os.access(f'{sls.failed}/{helper.name}/XXXX-XXXX.zip', os.F_OK)


@pytest.mark.asyncio
async def test_ok(helper_directory, monkeypatch):
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'alphabet', 'X')
    monkeypatch.setattr(helper, 'submit', awaitable(lambda _: HelperResult.OK))
    setup_categories(['sysreport'])

    zip = tempfile.NamedTemporaryFile(suffix='.zip')

    daemon, bus = await dbus_daemon(monkeypatch)
    usb = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Sysreport')
    iface = await usb.interface(f'{sls.constants.DBUS_NAME}.Sysreport')

    assert await iface.send_report(zip.name) == 'XXXX-XXXX'
    assert not os.access(f'{sls.pending}/{helper.name}/XXXX-XXXX.zip', os.F_OK)
    assert os.access(f'{sls.uploaded}/{helper.name}/XXXX-XXXX.zip', os.F_OK)


@pytest.mark.asyncio
async def test_metadata(helper_directory, monkeypatch):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.tags['friendly_id'] == 'XXXX-XXXX'
        assert self.message == 'System report XXXX-XXXX'
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'alphabet', 'X')
    setup_categories(['sysreport'])

    zip = tempfile.NamedTemporaryFile(suffix='.zip')
    assert await helper.send_report(zip.name) == 'XXXX-XXXX'
