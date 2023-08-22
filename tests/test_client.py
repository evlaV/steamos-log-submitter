# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import pytest
import time
import steamos_log_submitter as sls
import steamos_log_submitter.client
import steamos_log_submitter.daemon
import steamos_log_submitter.exceptions
from . import awaitable, setup_categories
from . import count_hits, helper_directory, mock_config, patch_module  # NOQA: F401
from .daemon import dbus_client, dbus_daemon  # NOQA: F401
from .dbus import mock_dbus, real_dbus  # NOQA: F401


@pytest.mark.asyncio
async def test_shutdown(dbus_client):
    daemon, client = await dbus_client
    await client.shutdown()
    assert not daemon._serving
    assert daemon._periodic_task is None
    assert daemon._async_trigger is None


@pytest.mark.asyncio
async def test_client_status(dbus_client, mock_config):
    daemon, client = await dbus_client
    assert not await client.status()
    await client.enable()
    assert await client.status()
    await client.disable()
    assert not await client.status()
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_list(dbus_client, monkeypatch, helper_directory):
    setup_categories(['test'])
    daemon, client = await dbus_client
    assert await client.list() == ['test']
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_get_log_level(dbus_client, mock_config):
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'INFO')
    daemon, client = await dbus_client
    assert await client.log_level() == 'INFO'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_set_log_level(dbus_client, mock_config):
    daemon, client = await dbus_client
    assert await client.log_level() != 'ERROR'
    await client.set_log_level('ERROR')
    assert await client.log_level() == 'ERROR'

    await client.set_log_level('warning')
    assert await client.log_level() == 'WARNING'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_set_log_level_invalid(dbus_client, mock_config):
    daemon, client = await dbus_client
    try:
        await client.set_log_level('VERBOSE')
        assert False
    except sls.exceptions.InvalidArgumentsError as e:
        assert e.data == {'level': 'VERBOSE'}
    assert await client.log_level() != 'VERBOSE'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_trigger(dbus_client, mock_config, monkeypatch, count_hits):
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    daemon, client = await dbus_client
    await client.enable()
    await client.trigger()
    assert count_hits.hits == 1
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_client_trigger_wait(dbus_client, mock_config, monkeypatch):
    async def trigger():
        await asyncio.sleep(0.1)

    monkeypatch.setattr(sls.runner, 'trigger', trigger)
    daemon, client = await dbus_client
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
async def test_client_trigger_wait2(dbus_client, mock_config, monkeypatch):
    async def trigger():
        await asyncio.sleep(0.1)

    monkeypatch.setattr(sls.runner, 'trigger', trigger)
    daemon, client = await dbus_client
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
async def test_helper_status(dbus_client, helper_directory):
    setup_categories(['test'])
    daemon, client = await dbus_client
    assert await client.helper_status() == {'test': {'enabled': True, 'collection': True, 'submission': True}}
    assert await client.helper_status(['test']) == {'test': {'enabled': True, 'collection': True, 'submission': True}}
    try:
        await client.helper_status(['test2'])
        assert False
    except sls.exceptions.InvalidArgumentsError:
        pass
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_enable_helpers(mock_config, dbus_client, helper_directory):
    mock_config.add_section('helpers.test')
    mock_config.set('helpers.test', 'enable', 'off')
    setup_categories(['test'])
    daemon, client = await dbus_client
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
async def test_set_steam_info(dbus_client, mock_config):
    daemon, client = await dbus_client
    await client.set_steam_info('deck_serial', 'FVAA12345')
    await client.set_steam_info('account_id', 12345)
    try:
        await client.set_steam_info('account_serial', 12345)
        assert False
    except sls.exceptions.InvalidArgumentsError:
        pass
    await daemon.shutdown()
