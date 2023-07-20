# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import concurrent.futures
import pytest
import time
import steamos_log_submitter as sls
import steamos_log_submitter.client
import steamos_log_submitter.daemon
from . import awaitable
from . import count_hits, fake_socket, mock_config  # NOQA: F401


def daemon_runner():
    daemon = sls.daemon.Daemon(exit_on_shutdown=True)
    loop = asyncio.new_event_loop()
    loop.create_task(daemon.start())
    loop.run_forever()


class SyncClient:
    def __init__(self):
        self.pool = concurrent.futures.ThreadPoolExecutor()

    def start(self):
        self.pool.submit(daemon_runner)
        time.sleep(0.1)
        self.client = sls.client.Client()

    def __getattr__(self, attr):
        return getattr(self.client, attr)


@pytest.fixture
def sync_client(fake_socket, mock_config, monkeypatch):
    monkeypatch.setattr(sls.helpers, 'list_helpers', lambda: ['test'])
    client = SyncClient()
    yield client
    client.shutdown()


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
