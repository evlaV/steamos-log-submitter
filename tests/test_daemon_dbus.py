# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import pytest
import steamos_log_submitter as sls
import steamos_log_submitter.helpers
import steamos_log_submitter.daemon
import steamos_log_submitter.dbus
import steamos_log_submitter.runner
import steamos_log_submitter.steam
from . import count_hits, helper_directory, mock_config, patch_module  # NOQA: F401
from .daemon import fake_socket  # NOQA: F401
from .dbus import real_dbus  # NOQA: F401


@pytest.fixture
async def dbus_daemon(fake_socket, real_dbus):
    bus = await real_dbus
    daemon = sls.daemon.Daemon()
    await daemon.start()
    return daemon, bus


@pytest.mark.asyncio
async def test_dbus(dbus_daemon):
    daemon, bus = await dbus_daemon
    dbemon = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter')
    assert {child for child in await dbemon.list_children()} == {
        '/com/valvesoftware/SteamOSLogSubmitter/Manager',
        '/com/valvesoftware/SteamOSLogSubmitter/helpers',
    }
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_list(dbus_daemon, helper_directory, monkeypatch):
    def list_helpers():
        return ['test']

    monkeypatch.setattr(sls.helpers, 'list_helpers', list_helpers)
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/helpers')
    assert {child for child in await manager.list_children()} == {
        '/com/valvesoftware/SteamOSLogSubmitter/helpers/Test',
    }
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_enabled(dbus_daemon, mock_config):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
    props = manager.properties('com.valvesoftware.SteamOSLogSubmitter.Manager')
    assert await props['Enabled'] is False
    await daemon.enable(True)
    assert await props['Enabled'] is True
    await props.set('Enabled', False)
    assert await props['Enabled'] is False
    await daemon.shutdown()
