# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import dbus_next as dbus
import json
import logging
import os
import pytest
import tempfile
import time

import steamos_log_submitter as sls
import steamos_log_submitter.helpers
import steamos_log_submitter.daemon
import steamos_log_submitter.runner

from . import awaitable, setup_categories, setup_logs, unreachable, CustomConfig
from . import count_hits, helper_directory, mock_config, open_shim, patch_module  # NOQA: F401
from .daemon import dbus_daemon  # NOQA: F401
from .dbus import MockDBusObject, MockDBusProperties
from .dbus import mock_dbus, real_dbus  # NOQA: F401

pytest_plugins = ('pytest_asyncio',)


@pytest.mark.asyncio
async def test_dbus(dbus_daemon):
    daemon, bus = await dbus_daemon
    dbemon = sls.dbus.DBusObject(bus, sls.constants.DBUS_ROOT)
    assert {child for child in await dbemon.list_children()} == {
        f'{sls.constants.DBUS_ROOT}/Manager',
        f'{sls.constants.DBUS_ROOT}/helpers',
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
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    iface = await manager.interface(f'{sls.constants.DBUS_NAME}.Manager')
    await iface.shutdown()
    assert not daemon._serving
    assert daemon._periodic_task is None
    assert daemon._async_trigger is None

    try:
        await iface.shutdown()
        assert False
    except dbus.errors.DBusError:
        pass

    root = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}')
    assert not await root.list_children()


@pytest.mark.asyncio
async def test_list(dbus_daemon, patch_module, monkeypatch):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers')
    assert {child for child in await manager.list_children()} == {
        f'{sls.constants.DBUS_ROOT}/helpers/Test',
    }
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_enabled(dbus_daemon, mock_config):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Manager')
    assert await props['Enabled'] is False
    await daemon.enable(True)
    assert await props['Enabled'] is True
    await props.set('Enabled', False)
    assert await props['Enabled'] is False
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_helper_enabled(count_hits, dbus_daemon, helper_directory, patch_module, mock_config):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': ''})
    patch_module.collect = awaitable(count_hits)
    patch_module.submit = awaitable(count_hits)

    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Test')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Helper')
    assert await props['Enabled'] is True

    await props.set('Enabled', False)
    assert await props['Enabled'] is False
    assert mock_config.get('helpers.test', 'enable') == 'off'
    await daemon.enable(True)
    await daemon.trigger(wait=True)
    assert count_hits.hits == 0

    await props.set('Enabled', True)
    assert await props['Enabled'] is True
    assert mock_config.get('helpers.test', 'enable') == 'on'
    await daemon.trigger(wait=True)
    assert count_hits.hits == 2

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_helper_collect_enabled(count_hits, dbus_daemon, helper_directory, patch_module, mock_config):
    setup_categories(['test'])
    patch_module.collect = awaitable(count_hits)
    patch_module.submit = awaitable(unreachable)

    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Test')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Helper')
    assert await props['Enabled'] is True
    assert await props['CollectEnabled'] is True

    await props.set('CollectEnabled', False)
    assert await props['CollectEnabled'] is False
    assert mock_config.get('helpers.test', 'collect') == 'off'
    await daemon.enable(True)
    await daemon.trigger(wait=True)
    assert count_hits.hits == 0

    await props.set('CollectEnabled', True)
    assert await props['CollectEnabled'] is True
    assert mock_config.get('helpers.test', 'collect') == 'on'
    await daemon.trigger(wait=True)
    assert count_hits.hits == 1

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_helper_submit_enabled(count_hits, dbus_daemon, helper_directory, monkeypatch, patch_module, mock_config):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': ''})
    monkeypatch.setattr(patch_module, 'collect', awaitable(lambda: False))
    monkeypatch.setattr(patch_module, 'submit', awaitable(count_hits))

    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Test')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Helper')
    assert await props['Enabled'] is True
    assert await props['SubmitEnabled'] is True

    await props.set('SubmitEnabled', False)
    assert await props['SubmitEnabled'] is False
    assert mock_config.get('helpers.test', 'submit') == 'off'
    await daemon.enable(True)
    await daemon.trigger(wait=True)
    assert count_hits.hits == 0

    await props.set('SubmitEnabled', True)
    assert await props['SubmitEnabled'] is True
    assert mock_config.get('helpers.test', 'submit') == 'on'
    await daemon.trigger(wait=True)
    assert count_hits.hits == 1

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_helper_child_services(count_hits, dbus_daemon, helper_directory, patch_module, mock_config):
    setup_categories(['test'])

    class PortalIface(dbus.service.ServiceInterface):
        def __init__(self):
            super().__init__('com.aperture.Portal')

        @dbus.service.method()
        async def Escape(self) -> 'i':  # type: ignore[name-defined] # NOQA: F821
            count_hits()
            return count_hits.hits

    patch_module.child_services = {
        'Portal': PortalIface()
    }

    daemon, bus = await dbus_daemon
    portal = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Test/Portal')
    iface = await portal.interface('com.aperture.Portal')

    assert count_hits.hits == 0
    assert await iface.escape() == 1
    assert count_hits.hits == 1

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_helper_extra_ifaces(count_hits, dbus_daemon, helper_directory, patch_module, mock_config):
    setup_categories(['test'])

    class MoondustIface(dbus.service.ServiceInterface):
        def __init__(self):
            super().__init__('com.aperture.MoonDust')

        @dbus.service.method()
        async def Breathe(self) -> 'i':  # type: ignore[name-defined] # NOQA: F821
            count_hits()
            return count_hits.hits

    patch_module.extra_ifaces = [MoondustIface()]

    daemon, bus = await dbus_daemon
    portal = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Test')
    iface = await portal.interface('com.aperture.MoonDust')

    assert count_hits.hits == 0
    assert await iface.breathe() == 1
    assert count_hits.hits == 1

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_inhibited(dbus_daemon, mock_config):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Manager')
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
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Manager')

    assert await props['LogLevel'] == logging.INFO
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_set_log_level(dbus_daemon, mock_config):
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'INFO')

    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Manager')

    await props.set('LogLevel', logging.WARNING)
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
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Manager')
    await props.set('LogLevel', logging.WARNING)

    sls.config.reload_config()
    assert not sls.config.config.has_option('logging', 'level')
    assert sls.config.local_config.has_section('logging')
    assert sls.config.local_config.get('logging', 'level') == 'WARNING'
    assert await props['LogLevel'] == logging.WARNING
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
async def test_trigger_collect(dbus_daemon, helper_directory, monkeypatch, count_hits, mock_config, patch_module):
    setup_categories(['test'])
    patch_module.collect = awaitable(count_hits)

    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Manager')

    assert await props['Enabled'] is False
    assert await props['CollectEnabled'] is True

    await props.set('CollectEnabled', False)
    assert await props['CollectEnabled'] is False
    await daemon.enable(True)
    await daemon.trigger(wait=True)
    assert count_hits.hits == 0

    await props.set('CollectEnabled', True)
    assert await props['CollectEnabled'] is True
    await daemon.trigger(wait=True)
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_trigger_submit(dbus_daemon, helper_directory, monkeypatch, count_hits, mock_config, patch_module):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': ''})
    patch_module.submit = awaitable(count_hits)

    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Manager')

    assert await props['Enabled'] is False
    assert await props['SubmitEnabled'] is True

    await props.set('SubmitEnabled', False)
    assert await props['SubmitEnabled'] is False
    await daemon.enable(True)
    await daemon.trigger(wait=True)
    assert count_hits.hits == 0

    await props.set('SubmitEnabled', True)
    assert await props['SubmitEnabled'] is True
    await daemon.trigger(wait=True)
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_trigger_called(dbus_daemon, monkeypatch, count_hits, mock_config):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    iface = await manager.interface(f'{sls.constants.DBUS_NAME}.Manager')
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
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    iface = await manager.interface(f'{sls.constants.DBUS_NAME}.Manager')
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
        await asyncio.sleep(0.1)
        count_hits()

    daemon, bus = await dbus_daemon
    await daemon.enable(True)
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    iface = await manager.interface(f'{sls.constants.DBUS_NAME}.Manager')
    monkeypatch.setattr(sls.runner, 'trigger', trigger)

    start = time.time()
    await iface.trigger_async()
    end = time.time()
    assert end - start < 0.1
    assert count_hits.hits == 0

    await iface.trigger_async()
    end = time.time()
    assert end - start < 0.1
    assert count_hits.hits == 0

    await asyncio.sleep(0.12)
    assert count_hits.hits == 1
    await asyncio.sleep(0.03)
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_trigger_dedup_slow(dbus_daemon, monkeypatch, mock_config, count_hits):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    iface = await manager.interface(f'{sls.constants.DBUS_NAME}.Manager')
    original_trigger = daemon._trigger

    async def trigger():
        await asyncio.sleep(0.1)
        count_hits()
        await original_trigger()

    daemon._trigger = trigger
    await daemon.enable(True)

    start = time.time()
    await iface.trigger_async()
    end = time.time()
    assert end - start < 0.1
    assert count_hits.hits == 0

    await iface.trigger_async()
    end = time.time()
    assert end - start < 0.1
    assert count_hits.hits == 0

    await asyncio.sleep(0.12)
    assert count_hits.hits == 1
    await asyncio.sleep(0.03)
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_trigger_dedup_slow_wait(dbus_daemon, monkeypatch, mock_config, count_hits):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    iface = await manager.interface(f'{sls.constants.DBUS_NAME}.Manager')
    original_trigger = daemon._trigger

    async def trigger():
        await asyncio.sleep(0.1)
        count_hits()
        await original_trigger()

    daemon._trigger = trigger
    await daemon.enable(True)

    start = time.time()
    await iface.trigger_async()
    end = time.time()
    assert end - start < 0.1
    assert count_hits.hits == 0

    await iface.trigger_async()
    end = time.time()
    assert end - start < 0.1
    assert count_hits.hits == 0

    await iface.trigger()
    assert count_hits.hits == 1
    await asyncio.sleep(0.12)
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
    monkeypatch.setattr(daemon, 'trigger', awaitable(count_hits))
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
    count_hits.ret = awaitable(lambda: None)()

    daemon = sls.daemon.Daemon()
    monkeypatch.setattr(daemon, '_trigger_periodic', count_hits)
    daemon.WAKEUP_DELAY = 0.01
    await daemon.start()
    await daemon.enable(True)

    props['ActiveState'] = 'active'
    await asyncio.sleep(0.02)
    assert daemon._suspend == 'active'
    assert count_hits.hits == 1

    props['ActiveState'] = 'inactive'
    await asyncio.sleep(0)
    assert count_hits.hits == 1
    await asyncio.sleep(0.02)
    assert daemon._suspend == 'inactive'
    assert count_hits.hits == 2


@pytest.mark.asyncio
async def test_suspend_double_wake(count_hits, mock_dbus, mock_config, monkeypatch):
    target = MockDBusObject('org.freedesktop.systemd1', '/org/freedesktop/systemd1/unit/suspend_2etarget', mock_dbus)
    target.properties['org.freedesktop.systemd1.Unit'] = {
        'ActiveState': 'inactive'
    }
    props = MockDBusProperties(target, 'org.freedesktop.systemd1.Unit')
    count_hits.ret = awaitable(lambda: None)()

    daemon = sls.daemon.Daemon()
    monkeypatch.setattr(daemon, '_trigger_periodic', count_hits)
    daemon.WAKEUP_DELAY = 0.01
    await daemon.start()
    await daemon.enable(True)

    assert daemon._suspend == 'inactive'
    assert count_hits.hits == 1
    props['ActiveState'] = 'inactive'
    await asyncio.sleep(0.02)
    assert daemon._suspend == 'inactive'
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_suspend_reschedule_early(count_hits, mock_dbus, mock_config, monkeypatch):
    target = MockDBusObject('org.freedesktop.systemd1', '/org/freedesktop/systemd1/unit/suspend_2etarget', mock_dbus)
    target.properties['org.freedesktop.systemd1.Unit'] = {
        'ActiveState': 'inactive'
    }
    props = MockDBusProperties(target, 'org.freedesktop.systemd1.Unit')

    daemon = sls.daemon.Daemon()
    monkeypatch.setattr(daemon, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(time, 'time', lambda: 100000)
    daemon.WAKEUP_DELAY = 0.01
    daemon.INTERVAL = 5
    await daemon.start()
    await daemon.enable(True)

    props['ActiveState'] = 'active'
    await asyncio.sleep(0.02)
    assert daemon._suspend == 'active'
    assert count_hits.hits == 0

    monkeypatch.setattr(time, 'time', lambda: 200000)
    props['ActiveState'] = 'inactive'
    await asyncio.sleep(0)
    assert count_hits.hits == 0
    await asyncio.sleep(0.02)
    assert daemon._suspend == 'inactive'
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_suspend_reschedule_late(count_hits, mock_dbus, mock_config, monkeypatch):
    target = MockDBusObject('org.freedesktop.systemd1', '/org/freedesktop/systemd1/unit/suspend_2etarget', mock_dbus)
    target.properties['org.freedesktop.systemd1.Unit'] = {
        'ActiveState': 'inactive'
    }
    props = MockDBusProperties(target, 'org.freedesktop.systemd1.Unit')

    daemon = sls.daemon.Daemon()
    monkeypatch.setattr(daemon, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(time, 'time', lambda: 100000)
    daemon.WAKEUP_DELAY = 0.01
    daemon.STARTUP = 0.06
    await daemon.start()
    await daemon.enable(True)

    props['ActiveState'] = 'active'
    await asyncio.sleep(0.02)
    assert daemon._suspend == 'active'
    assert count_hits.hits == 0

    monkeypatch.setattr(time, 'time', lambda: 100000.03)
    props['ActiveState'] = 'inactive'
    await asyncio.sleep(0)
    assert count_hits.hits == 0
    assert daemon._suspend == 'inactive'

    monkeypatch.setattr(time, 'time', lambda: 100000.05)
    await asyncio.sleep(0.02)
    assert count_hits.hits == 0

    monkeypatch.setattr(time, 'time', lambda: 100000.08)
    await asyncio.sleep(0.02)
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_log_passthru(dbus_daemon, mock_config):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    iface = await manager.interface(f'{sls.constants.DBUS_NAME}.Manager')

    tmpdir = tempfile.TemporaryDirectory(prefix='sls-')
    sls.logging.reconfigure_logging(f'{tmpdir.name}/log')

    await iface.log(60 * 60 * 24, 'steamos_log_submitter.test', logging.ERROR, 'foo')
    assert os.access(f'{tmpdir.name}/log', os.F_OK)
    with open(f'{tmpdir.name}/log') as f:
        log = f.read()

    assert 'ERROR' in log
    assert 'test' in log
    assert 'foo' in log
    assert '1970' in log

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_log_invalid_level(dbus_daemon, mock_config):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    iface = await manager.interface(f'{sls.constants.DBUS_NAME}.Manager')

    try:
        await iface.log(0.0, 'steamos_log_submitter.test', 123, 'foo')
    except dbus.errors.DBusError as e:
        assert e.type == sls.exceptions.InvalidArgumentsError.name
        assert json.loads(e.text) == {'level': 123}

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_telemetry_ids(dbus_daemon, mock_config, open_shim):
    daemon, bus = await dbus_daemon
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    props = manager.properties(f'{sls.constants.DBUS_NAME}.Manager')

    open_shim.enoent()

    mock_config.add_section('steam')
    assert sls.util.telemetry_unit_id() is None
    assert await props['UnitId'] == ''

    def check_file(fname):
        return b'12345678'

    open_shim.cb(check_file)

    assert sls.util.telemetry_unit_id() is not None
    assert await props['UnitId'] == sls.util.telemetry_unit_id()

    await daemon.shutdown()
