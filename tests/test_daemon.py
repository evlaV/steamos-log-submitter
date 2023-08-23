# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import dbus_next as dbus
import pytest
import time
import steamos_log_submitter as sls
import steamos_log_submitter.helpers
import steamos_log_submitter.daemon
import steamos_log_submitter.runner
import steamos_log_submitter.steam
from . import awaitable, CustomConfig
from . import count_hits, mock_config, patch_module  # NOQA: F401
from .daemon import dbus_daemon  # NOQA: F401
from .dbus import MockDBusObject, MockDBusProperties
from .dbus import mock_dbus, real_dbus  # NOQA: F401

pytest_plugins = ('pytest_asyncio',)


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
async def test_shutdown(dbus_daemon):
    daemon, bus = await dbus_daemon
    await daemon.shutdown()
    assert not daemon._serving
    assert daemon._periodic_task is None
    assert daemon._async_trigger is None


@pytest.mark.asyncio
async def test_shutdown_dbus(dbus_daemon):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
    iface = await manager.interface('com.valvesoftware.SteamOSLogSubmitter.Manager')
    await iface.shutdown()
    assert not daemon._serving
    assert daemon._periodic_task is None
    assert daemon._async_trigger is None

    try:
        await iface.shutdown()
        assert False
    except dbus.errors.DBusError:
        pass

    root = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter')
    assert not await root.list_children()


@pytest.mark.asyncio
async def test_list(dbus_daemon, patch_module, monkeypatch):
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


@pytest.mark.asyncio
async def test_helper_enabled(dbus_daemon, patch_module, mock_config, monkeypatch):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/helpers/Test')
    props = manager.properties('com.valvesoftware.SteamOSLogSubmitter.Helper')
    assert await props['Enabled'] is True
    await props.set('Enabled', False)
    assert await props['Enabled'] is False
    assert mock_config.get('helpers.test', 'enable') == 'off'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_helper_collect_enabled(dbus_daemon, patch_module, mock_config, monkeypatch):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/helpers/Test')
    props = manager.properties('com.valvesoftware.SteamOSLogSubmitter.Helper')
    assert await props['CollectEnabled'] is True
    await props.set('CollectEnabled', False)
    assert await props['CollectEnabled'] is False
    assert mock_config.get('helpers.test', 'collect') == 'off'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_helper_submit_enabled(dbus_daemon, patch_module, mock_config, monkeypatch):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/helpers/Test')
    props = manager.properties('com.valvesoftware.SteamOSLogSubmitter.Helper')
    assert await props['SubmitEnabled'] is True
    await props.set('SubmitEnabled', False)
    assert await props['SubmitEnabled'] is False
    assert mock_config.get('helpers.test', 'submit') == 'off'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_inhibited(dbus_daemon, mock_config):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
    props = manager.properties('com.valvesoftware.SteamOSLogSubmitter.Manager')
    assert await props['Inhibited'] is False
    await daemon.inhibit(True)
    assert await props['Inhibited'] is True
    await props.set('Inhibited', False)
    assert await props['Inhibited'] is False
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_get_log_level(dbus_daemon, mock_config):
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'INFO')

    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
    props = manager.properties('com.valvesoftware.SteamOSLogSubmitter.Manager')

    assert await props['LogLevel'] == 'INFO'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_set_log_level(dbus_daemon, mock_config):
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'INFO')

    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
    props = manager.properties('com.valvesoftware.SteamOSLogSubmitter.Manager')

    await props.set('LogLevel', 'WARNING')
    assert mock_config.get('logging', 'level') == 'WARNING'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_set_log_level_migrate(dbus_daemon, monkeypatch):
    custom_config = CustomConfig(monkeypatch)
    custom_config.user.add_section('logging')
    custom_config.user.set('logging', 'level', 'WARNING')
    custom_config.write()

    sls.config.reload_config()
    assert sls.config.local_config_path == custom_config.local_file.name
    assert sls.config.user_config_path == custom_config.user_file.name
    assert sls.config.config.has_section('logging')
    assert sls.config.config.get('logging', 'level') == 'WARNING'
    assert not sls.config.local_config.has_section('logging')

    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
    props = manager.properties('com.valvesoftware.SteamOSLogSubmitter.Manager')
    await props.set('LogLevel', 'WARNING')

    sls.config.reload_config()
    assert not sls.config.config.has_option('logging', 'level')
    assert sls.config.local_config.has_section('logging')
    assert sls.config.local_config.get('logging', 'level') == 'WARNING'
    assert await props['LogLevel'] == 'WARNING'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_periodic(dbus_daemon, monkeypatch, count_hits, mock_config):
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(sls.daemon.Daemon, 'STARTUP', 0.05)
    monkeypatch.setattr(sls.daemon.Daemon, 'INTERVAL', 0.06)

    start = time.time()
    daemon, bus = await dbus_daemon
    await daemon.enable(True)

    assert count_hits.hits == 0
    await asyncio.sleep(0.06)
    assert mock_config.has_section('daemon')
    assert mock_config.has_option('daemon', 'last_trigger')
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) - start < 0.07

    await asyncio.sleep(0.13)
    assert count_hits.hits == 3
    assert float(mock_config.get('daemon', 'last_trigger')) - start > 0.17

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_periodic_after_startup(dbus_daemon, monkeypatch, count_hits, mock_config):
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(sls.daemon.Daemon, 'STARTUP', 0.08)
    monkeypatch.setattr(sls.daemon.Daemon, 'INTERVAL', 0.06)

    mock_config.add_section('daemon')
    start = time.time()
    mock_config.set('daemon', 'last_trigger', str(start + 0.05))
    daemon, bus = await dbus_daemon
    await daemon.enable(True)

    assert count_hits.hits == 0
    await asyncio.sleep(0.06)
    assert count_hits.hits == 0
    assert float(mock_config.get('daemon', 'last_trigger')) - start > 0.04

    await asyncio.sleep(0.06)
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) - start > 0.11

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_periodic_before_startup(dbus_daemon, monkeypatch, count_hits, mock_config):
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(sls.daemon.Daemon, 'STARTUP', 0.05)
    monkeypatch.setattr(sls.daemon.Daemon, 'INTERVAL', 0.2)

    mock_config.add_section('daemon')
    mock_config.set('daemon', 'last_trigger', str(time.time() - 0.2))

    start = time.time()
    daemon, bus = await dbus_daemon
    await daemon.enable(True)

    assert count_hits.hits == 0
    await asyncio.sleep(0.06)
    assert count_hits.hits == 1
    end = float(mock_config.get('daemon', 'last_trigger'))
    assert end - start > 0

    await asyncio.sleep(0.07)
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) == end

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_periodic_before_startup2(dbus_daemon, monkeypatch, count_hits, mock_config):
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(sls.daemon.Daemon, 'STARTUP', 0.08)
    monkeypatch.setattr(sls.daemon.Daemon, 'INTERVAL', 0.2)

    mock_config.add_section('sls')
    mock_config.set('sls', 'enable', 'on')
    mock_config.add_section('daemon')
    mock_config.set('daemon', 'last_trigger', str(time.time() - 0.2))

    start = time.time()
    daemon, bus = await dbus_daemon
    assert count_hits.hits == 0
    await asyncio.sleep(0.09)
    assert count_hits.hits == 1
    end = float(mock_config.get('daemon', 'last_trigger'))
    assert end - start > 0

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_periodic_delay(dbus_daemon, monkeypatch, count_hits, mock_config):
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(sls.daemon.Daemon, 'STARTUP', 0.05)
    monkeypatch.setattr(sls.daemon.Daemon, 'INTERVAL', 0.07)

    start = time.time()
    daemon, bus = await dbus_daemon
    await daemon.enable(True)

    assert count_hits.hits == 0
    await asyncio.sleep(0.06)
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) - start > 0.05

    await asyncio.sleep(0.03)
    await daemon.trigger(wait=True)
    assert count_hits.hits == 2
    end = float(mock_config.get('daemon', 'last_trigger'))
    assert end - start > 0.09
    assert end - start < 0.14

    await asyncio.sleep(0.03)
    assert count_hits.hits == 2
    assert float(mock_config.get('daemon', 'last_trigger')) == end

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_set_steam_info(dbus_daemon, mock_config):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
    iface = await manager.interface('com.valvesoftware.SteamOSLogSubmitter.Manager')

    await iface.set_steam_info('account_name', 'gaben')
    assert sls.steam.get_steam_account_name() == 'gaben'

    await iface.set_steam_info('account_id', '12345')
    assert sls.steam.get_steam_account_id() == 12345

    await iface.set_steam_info('deck_serial', 'HEV Mark IV')
    assert sls.steam.get_deck_serial() == 'HEV Mark IV'

    try:
        await iface.set_steam_info('invalid', 'foo')
        assert False
    except dbus.errors.DBusError as e:
        assert e.type == 'com.valvesoftware.SteamOSLogSubmitter.InvalidArgumentsError'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_inhibit(dbus_daemon, monkeypatch, count_hits, mock_config):
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(sls.daemon.Daemon, 'STARTUP', 0.05)
    monkeypatch.setattr(sls.daemon.Daemon, 'INTERVAL', 0.04)
    start = time.time()
    daemon, bus = await dbus_daemon
    await daemon.enable(True)

    assert count_hits.hits == 0
    await asyncio.sleep(0.06)
    assert mock_config.has_section('daemon')
    assert mock_config.has_option('daemon', 'last_trigger')
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) - start < 0.06

    await daemon.inhibit(True)
    assert count_hits.hits == 1
    assert mock_config.has_option('sls', 'inhibit')
    assert mock_config.get('sls', 'inhibit') == 'on'

    await asyncio.sleep(0.09)
    assert count_hits.hits == 1

    await daemon.trigger(wait=True)
    assert count_hits.hits == 1

    await daemon.inhibit(False)
    assert mock_config.has_option('sls', 'inhibit')
    assert mock_config.get('sls', 'inhibit') == 'off'
    await asyncio.sleep(0)
    assert count_hits.hits == 2

    await daemon.trigger(wait=True)
    assert count_hits.hits == 3

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_trigger_called(dbus_daemon, monkeypatch, count_hits, mock_config):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
    iface = await manager.interface('com.valvesoftware.SteamOSLogSubmitter.Manager')
    monkeypatch.setattr(sls.runner, 'collect', awaitable(count_hits))
    monkeypatch.setattr(sls.runner, 'submit', awaitable(count_hits))

    await daemon.enable(True)
    await iface.trigger()
    assert count_hits.hits == 2
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_trigger_wait(dbus_daemon, monkeypatch, mock_config, count_hits):
    async def trigger():
        await asyncio.sleep(0.1)
        count_hits()

    daemon, bus = await dbus_daemon
    await daemon.enable(True)
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
    iface = await manager.interface('com.valvesoftware.SteamOSLogSubmitter.Manager')
    monkeypatch.setattr(sls.runner, 'trigger', trigger)

    start = time.time()
    await iface.trigger_async()
    end = time.time()
    assert end - start < 0.1
    assert count_hits.hits == 0

    start = time.time()
    await iface.trigger()
    end = time.time()
    assert end - start >= 0.1
    assert count_hits.hits in (1, 2)


@pytest.mark.asyncio
async def test_trigger_dedup(dbus_daemon, monkeypatch, mock_config, count_hits):
    async def trigger():
        await asyncio.sleep(0.15)
        count_hits()

    daemon, bus = await dbus_daemon
    await daemon.enable(True)
    manager = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/Manager')
    iface = await manager.interface('com.valvesoftware.SteamOSLogSubmitter.Manager')
    monkeypatch.setattr(sls.runner, 'trigger', trigger)

    start = time.time()
    await iface.trigger_async()
    end = time.time()
    assert end - start < 0.15
    assert count_hits.hits == 0

    await iface.trigger_async()
    end = time.time()
    assert end - start < 0.15
    assert count_hits.hits == 0

    await asyncio.sleep(0.17)
    assert count_hits.hits == 1
    await asyncio.sleep(0.03)
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_trigger_then_disable(count_hits, dbus_daemon, mock_config, monkeypatch):
    async def trigger():
        await asyncio.sleep(0.05)
        count_hits()

    daemon, bus = await dbus_daemon
    monkeypatch.setattr(sls.runner, 'trigger', trigger)

    await daemon.enable(True)

    assert count_hits.hits == 0
    await daemon.trigger(wait=False)
    assert count_hits.hits == 0

    await daemon.enable(False)
    assert count_hits.hits == 1
    await daemon.trigger(wait=True)
    assert count_hits.hits == 1

    await daemon.enable(True)
    assert count_hits.hits == 1

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_trigger_then_inhibit(count_hits, dbus_daemon, mock_config, monkeypatch):
    async def trigger():
        await asyncio.sleep(0.05)
        count_hits()

    daemon, bus = await dbus_daemon
    monkeypatch.setattr(sls.runner, 'trigger', trigger)

    await daemon.enable(True)
    await daemon.inhibit(False)

    assert count_hits.hits == 0
    await daemon.trigger(wait=False)
    assert count_hits.hits == 0

    await daemon.inhibit(True)
    assert count_hits.hits == 1
    await daemon.trigger(wait=True)
    assert count_hits.hits == 1

    await daemon.inhibit(False)
    assert count_hits.hits == 1

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_suspend_sleep(count_hits, mock_dbus, mock_config, monkeypatch):
    target = MockDBusObject('org.freedesktop.systemd1', '/org/freedesktop/systemd1/unit/suspend_2etarget', mock_dbus)
    target.properties['org.freedesktop.systemd1.Unit'] = {
        'ActiveState': 'inactive'
    }
    props = MockDBusProperties(target, 'org.freedesktop.systemd1.Unit')

    daemon = sls.daemon.Daemon()
    daemon.trigger = awaitable(count_hits)
    daemon.WAKEUP_DELAY = 0.01
    await daemon.start()

    assert daemon._suspend == 'inactive'
    props['ActiveState'] = 'active'
    await asyncio.sleep(0.02)
    assert daemon._suspend == 'active'
    assert count_hits.hits == 0


@pytest.mark.asyncio
async def test_suspend_wake(count_hits, mock_dbus, mock_config, monkeypatch):
    target = MockDBusObject('org.freedesktop.systemd1', '/org/freedesktop/systemd1/unit/suspend_2etarget', mock_dbus)
    target.properties['org.freedesktop.systemd1.Unit'] = {
        'ActiveState': 'inactive'
    }
    props = MockDBusProperties(target, 'org.freedesktop.systemd1.Unit')

    daemon = sls.daemon.Daemon()
    daemon.trigger = awaitable(count_hits)
    daemon.WAKEUP_DELAY = 0.01
    await daemon.start()

    props['ActiveState'] = 'active'
    await asyncio.sleep(0.02)
    assert daemon._suspend == 'active'
    props['ActiveState'] = 'inactive'
    await asyncio.sleep(0.02)
    assert daemon._suspend == 'inactive'
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_suspend_double_wake(count_hits, mock_dbus, mock_config, monkeypatch):
    target = MockDBusObject('org.freedesktop.systemd1', '/org/freedesktop/systemd1/unit/suspend_2etarget', mock_dbus)
    target.properties['org.freedesktop.systemd1.Unit'] = {
        'ActiveState': 'inactive'
    }
    props = MockDBusProperties(target, 'org.freedesktop.systemd1.Unit')

    daemon = sls.daemon.Daemon()
    daemon.trigger = awaitable(count_hits)
    daemon.WAKEUP_DELAY = 0.01
    await daemon.start()

    assert daemon._suspend == 'inactive'
    props['ActiveState'] = 'inactive'
    await asyncio.sleep(0.02)
    assert daemon._suspend == 'inactive'
    assert count_hits.hits == 0
