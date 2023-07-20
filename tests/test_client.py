# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import time
import steamos_log_submitter as sls
import steamos_log_submitter.client
import steamos_log_submitter.daemon
from . import awaitable
from . import count_hits, fake_socket, mock_config, sync_client  # NOQA: F401


def test_client_status(sync_client):
    sync_client.start()
    assert not sync_client.status()
    sync_client.enable()
    assert sync_client.status()
    sync_client.disable()
    assert not sync_client.status()


def test_client_list(sync_client):
    sync_client.start()
    assert sync_client.list() == ['test']


def test_client_get_log_level(sync_client, mock_config):
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'INFO')
    sync_client.start()
    assert sync_client.log_level() == 'INFO'


def test_client_set_log_level(sync_client, mock_config):
    sync_client.start()
    assert sync_client.log_level() != 'ERROR'
    sync_client.set_log_level('ERROR')
    assert sync_client.log_level() == 'ERROR'


def test_client_trigger(sync_client, mock_config, monkeypatch, count_hits):
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    sync_client.start()
    sync_client.trigger()
    assert count_hits.hits == 1


def test_client_trigger_wait(sync_client, mock_config, monkeypatch):
    async def trigger():
        await asyncio.sleep(0.1)

    monkeypatch.setattr(sls.runner, 'trigger', trigger)
    sync_client.start()

    start = time.time()
    sync_client.trigger(False)
    end = time.time()
    assert end - start < 0.1

    start = time.time()
    sync_client.trigger(True)
    end = time.time()
    assert end - start >= 0.1


def test_enable_helpers(sync_client):
    sync_client.start()
    sync_client.enable_helpers(['test'])
    try:
        sync_client.enable_helpers(['test2'])
        assert False
    except sls.client.InvalidArgumentsError:
        pass


def test_set_steam_info(sync_client):
    sync_client.start()
    sync_client.set_steam_info('deck_serial', 'FVAA12345')
    sync_client.set_steam_info('account_id', 12345)
    try:
        sync_client.set_steam_info('account_serial', 12345)
        assert False
    except sls.client.InvalidArgumentsError:
        pass
