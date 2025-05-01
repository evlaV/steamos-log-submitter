# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import logging
import os
import pytest
import tempfile
import time

import steamos_log_submitter as sls
import steamos_log_submitter.client
import steamos_log_submitter.daemon
import steamos_log_submitter.exceptions
from steamos_log_submitter.constants import DBUS_NAME, DBUS_ROOT
from steamos_log_submitter.types import DBusEncodable

from . import awaitable, setup_categories, setup_logs
from . import count_hits, helper_directory, mock_config, patch_module  # NOQA: F401
from .daemon import dbus_client
from .dbus import mock_dbus  # NOQA: F401
from .dbus import real_dbus


@pytest.mark.asyncio
async def test_inactive(monkeypatch):
    bus = await real_dbus(monkeypatch)
    client = sls.client.Client(bus=bus)
    try:
        await client._connect()
        assert False
    except ConnectionRefusedError:
        pass


@pytest.mark.asyncio
async def test_shutdown(monkeypatch):
    daemon, client = await dbus_client(monkeypatch)
    await client.shutdown()
    assert not daemon._serving
    assert daemon._periodic_task is None
    assert daemon._async_trigger is None


@pytest.mark.asyncio
async def test_client_status(mock_config, monkeypatch):
    daemon, client = await dbus_client(monkeypatch)
    assert not await client.status()
    await client.enable()
    assert await client.status()
    await client.disable()
    assert not await client.status()
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_subscribe_enable(count_hits, mock_config, monkeypatch):
    expected = True

    async def test_enabled(iface: str, prop: str, value: DBusEncodable) -> None:
        assert iface == f'{DBUS_NAME}.Manager'
        assert prop == 'Enabled'
        assert value is expected
        count_hits()

    daemon, client = await dbus_client(monkeypatch)
    manager = sls.dbus.DBusObject(client._bus, f'{DBUS_ROOT}/Manager')
    props = manager.properties(f'{DBUS_NAME}.Manager')
    await props.subscribe('Enabled', test_enabled)

    expected = True
    await client.enable()
    assert count_hits.hits == 1

    expected = False
    await client.disable()
    assert count_hits.hits == 2

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_list(helper_directory, monkeypatch):
    setup_categories(['test'])
    daemon, client = await dbus_client(monkeypatch)
    assert await client.list() == ['test']
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_get_log_level(mock_config, monkeypatch):
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'INFO')
    daemon, client = await dbus_client(monkeypatch)
    assert await client.log_level() == logging.INFO
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_set_log_level(mock_config, monkeypatch):
    daemon, client = await dbus_client(monkeypatch)
    assert await client.log_level() != logging.ERROR
    await client.set_log_level(logging.ERROR)
    assert await client.log_level() == logging.ERROR

    await client.set_log_level(logging.WARNING)
    assert await client.log_level() == logging.WARNING
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_set_log_level_invalid(mock_config, monkeypatch):
    daemon, client = await dbus_client(monkeypatch)
    try:
        await client.set_log_level(123)
        assert False
    except sls.exceptions.InvalidArgumentsError as e:
        assert e.data == {'level': 123}
    assert await client.log_level() != 123
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_trigger(mock_config, monkeypatch, count_hits):
    count_hits.ret = [], []
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    daemon, client = await dbus_client(monkeypatch)
    await client.enable()
    await client.trigger()
    assert count_hits.hits == 1
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_trigger_wait(mock_config, monkeypatch):
    async def trigger():
        await asyncio.sleep(0.1)
        return [], []

    monkeypatch.setattr(sls.runner, 'trigger', trigger)
    daemon, client = await dbus_client(monkeypatch)
    await client.enable()

    start = time.time()
    await client.trigger(False)
    end = time.time()
    assert end - start < 0.1

    start = time.time()
    await client.trigger(True)
    end = time.time()
    assert end - start >= 0.1
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_trigger_wait2(mock_config, monkeypatch):
    async def trigger():
        await asyncio.sleep(0.1)
        return [], []

    monkeypatch.setattr(sls.runner, 'trigger', trigger)
    daemon, client = await dbus_client(monkeypatch)
    await client.enable()

    start = time.time()
    await client.trigger(True)
    end = time.time()
    assert end - start >= 0.1

    start = time.time()
    await client.trigger(False)
    end = time.time()
    assert end - start < 0.1
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_helper_status(helper_directory, monkeypatch):
    setup_categories(['test'])
    daemon, client = await dbus_client(monkeypatch)
    assert await client.helper_status() == {'test': {'enabled': True, 'collection': True, 'submission': True}}
    assert await client.helper_status(['test']) == {'test': {'enabled': True, 'collection': True, 'submission': True}}
    try:
        await client.helper_status(['test2'])
        assert False
    except sls.exceptions.InvalidArgumentsError:
        pass
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_enable_helpers(helper_directory, mock_config, monkeypatch):
    mock_config.add_section('helpers.test')
    mock_config.set('helpers.test', 'enable', 'off')
    setup_categories(['test'])
    daemon, client = await dbus_client(monkeypatch)
    assert (await client.helper_status(['test']))['test']['enabled'] is False
    await client.enable_helpers(['test'])
    assert (await client.helper_status(['test']))['test']['enabled'] is True
    try:
        await client.enable_helpers(['test2'])
        assert False
    except sls.exceptions.InvalidArgumentsError:
        pass
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_subscribe_enable_helper(count_hits, helper_directory, mock_config, monkeypatch):
    expected = True

    async def test_enabled(iface: str, prop: str, value: DBusEncodable) -> None:
        assert iface == f'{DBUS_NAME}.Helper'
        assert prop == 'Enabled'
        assert value is expected
        count_hits()

    mock_config.add_section('helpers.test')
    mock_config.set('helpers.test', 'enable', 'off')
    setup_categories(['test'])

    daemon, client = await dbus_client(monkeypatch)
    manager = sls.dbus.DBusObject(client._bus, f'{DBUS_ROOT}/helpers/Test')
    props = manager.properties(f'{DBUS_NAME}.Helper')
    await props.subscribe('Enabled', test_enabled)

    expected = True
    await client.enable_helpers(['test'])
    assert count_hits.hits == 1

    expected = False
    await client.disable_helpers(['test'])
    assert count_hits.hits == 2

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_list_pending(helper_directory, monkeypatch):
    setup_categories(['test', 'test2', 'test3'])
    setup_logs(helper_directory, {'test/a': '', 'test/b': '', 'test2/c': ''})
    daemon, client = await dbus_client(monkeypatch)

    assert set(await client.list_pending()) == {'test/a', 'test/b', 'test2/c'}
    assert set(await client.list_pending(['test'])) == {'test/a', 'test/b'}
    assert set(await client.list_pending(['test2'])) == {'test2/c'}
    assert set(await client.list_pending(['test3'])) == set()
    assert set(await client.list_pending(['test', 'test2'])) == {'test/a', 'test/b', 'test2/c'}
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_list_uploaded(helper_directory, monkeypatch, patch_module):
    setup_categories(['test', 'test2', 'test3'])
    setup_logs(helper_directory, {'test/a': '', 'test/b': '', 'test2/c': ''})
    patch_module.submit = awaitable(lambda *args: sls.helpers.HelperResult.OK)
    daemon, client = await dbus_client(monkeypatch)

    assert set(await client.list_pending()) == {'test/a', 'test/b', 'test2/c'}
    assert set(await client.list_pending(['test'])) == {'test/a', 'test/b'}
    assert set(await client.list_pending(['test2'])) == {'test2/c'}
    assert set(await client.list_pending(['test3'])) == set()
    assert set(await client.list_pending(['test', 'test2'])) == {'test/a', 'test/b', 'test2/c'}

    await client.enable()
    await client.trigger(True)

    assert not await client.list_pending()
    assert not await client.list_pending(['test'])
    assert not await client.list_pending(['test2'])
    assert not await client.list_pending(['test3'])
    assert not await client.list_pending(['test', 'test2'])

    assert set(await client.list_uploaded()) == {'test/a', 'test/b', 'test2/c'}
    assert set(await client.list_uploaded(['test'])) == {'test/a', 'test/b'}
    assert set(await client.list_uploaded(['test2'])) == {'test2/c'}
    assert set(await client.list_uploaded(['test3'])) == set()
    assert set(await client.list_uploaded(['test', 'test2'])) == {'test/a', 'test/b', 'test2/c'}

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_list_failed(helper_directory, monkeypatch, patch_module):
    setup_categories(['test', 'test2', 'test3'])
    setup_logs(helper_directory, {'test/a': '', 'test/b': '', 'test2/c': ''})
    patch_module.submit = awaitable(lambda *args: sls.helpers.HelperResult.PERMANENT_ERROR)
    daemon, client = await dbus_client(monkeypatch)

    assert set(await client.list_pending()) == {'test/a', 'test/b', 'test2/c'}
    assert set(await client.list_pending(['test'])) == {'test/a', 'test/b'}
    assert set(await client.list_pending(['test2'])) == {'test2/c'}
    assert set(await client.list_pending(['test3'])) == set()
    assert set(await client.list_pending(['test', 'test2'])) == {'test/a', 'test/b', 'test2/c'}

    await client.enable()
    await client.trigger(True)

    assert not await client.list_pending()
    assert not await client.list_pending(['test'])
    assert not await client.list_pending(['test2'])
    assert not await client.list_pending(['test3'])
    assert not await client.list_pending(['test', 'test2'])

    assert set(await client.list_failed()) == {'test/a', 'test/b', 'test2/c'}
    assert set(await client.list_failed(['test'])) == {'test/a', 'test/b'}
    assert set(await client.list_failed(['test2'])) == {'test2/c'}
    assert set(await client.list_failed(['test3'])) == set()
    assert set(await client.list_failed(['test', 'test2'])) == {'test/a', 'test/b', 'test2/c'}

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_extract(helper_directory, monkeypatch):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': 'abc'})
    daemon, client = await dbus_client(monkeypatch)

    assert await client.extract('test', 'log', 'failed') is None
    assert await client.extract('test', 'log', 'uploaded') is None

    with await client.extract('test', 'log') as f:
        assert f.read() == b'abc'

    with await client.extract('test', 'log', 'pending') as f:
        assert f.read() == b'abc'

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_collect(helper_directory, monkeypatch, patch_module):
    setup_categories(['test', 'test2', 'test3'])
    setup_logs(helper_directory, {'test/a': '', 'test/b': '', 'test2/c': ''})
    daemon, client = await dbus_client(monkeypatch)

    assert set(await client.collect(['test'])) == {'test/a', 'test/b'}
    assert set(await client.collect(['test2'])) == {'test2/c'}
    assert set(await client.collect(['test3'])) == set()
    assert not await client.collect(['test'])
    assert not await client.collect(['test2'])
    assert not await client.collect(['test3'])
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_log_passthru(mock_config, monkeypatch):
    daemon, client = await dbus_client(monkeypatch)
    tmpdir = tempfile.TemporaryDirectory(prefix='sls-')
    sls.logging.reconfigure_logging(f'{tmpdir.name}/log')

    await client.log('steamos_log_submitter.test', logging.ERROR, 'foo')
    assert os.access(f'{tmpdir.name}/log', os.F_OK)
    with open(f'{tmpdir.name}/log') as f:
        log = f.read()

    assert 'ERROR' in log
    assert 'test' in log
    assert 'foo' in log

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_log_invalid_level(mock_config, monkeypatch):
    daemon, client = await dbus_client(monkeypatch)
    try:
        await client.log('steamos_log_submitter.test', 123, 'foo')
    except sls.exceptions.InvalidArgumentsError as e:
        assert e.data == {'level': 123}

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_version(mock_config, monkeypatch):
    daemon, client = await dbus_client(monkeypatch)

    assert await client.version() == sls.__version__


@pytest.mark.asyncio
async def test_unit_id(monkeypatch):
    daemon, client = await dbus_client(monkeypatch)

    monkeypatch.setattr(sls.util, "telemetry_unit_id", lambda: "foo")
    assert await client.unit_id() == "foo"

    monkeypatch.setattr(sls.util, "telemetry_unit_id", lambda: None)
    assert not await client.unit_id()
