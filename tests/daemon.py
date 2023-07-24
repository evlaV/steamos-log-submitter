# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import concurrent.futures
import os
import pytest
import time
import threading
import steamos_log_submitter as sls
import steamos_log_submitter.daemon
from .dbus import MockDBusObject
from .dbus import mock_dbus  # NOQA: F401


@pytest.fixture
def fake_socket(monkeypatch):
    prefix = int((time.time() % 1) * 0x400000)
    fakesocket = f'{prefix:06x}.socket'
    monkeypatch.setattr(sls.daemon, 'socket', fakesocket)
    yield fakesocket

    if os.access(fakesocket, os.F_OK):
        os.unlink(fakesocket)


@pytest.fixture(autouse=True)
def systemd_object(mock_dbus):
    MockDBusObject('org.freedesktop.systemd1', '/org/freedesktop/systemd1/unit/suspend_2etarget', mock_dbus)


def daemon_runner(ev, box):
    daemon = sls.daemon.Daemon(exit_on_shutdown=True)
    loop = asyncio.new_event_loop()

    async def start():
        try:
            await daemon.start()
        except Exception as e:
            box.append(e)
            ev.set()
            raise
        ev.set()
    loop.create_task(start())
    loop.run_forever()


class SyncClient:
    def __init__(self):
        self.pool = concurrent.futures.ThreadPoolExecutor()
        self.client = None

    def start(self):
        ev = threading.Event()
        box = []
        self.pool.submit(daemon_runner, ev, box)
        ev.wait()
        if box:
            raise box[0]
        self.client = sls.client.Client()

    def __getattr__(self, attr):
        return getattr(self.client, attr)


@pytest.fixture
def sync_client(fake_socket, mock_config, monkeypatch):
    monkeypatch.setattr(sls.helpers, 'list_helpers', lambda: ['test'])
    client = SyncClient()
    yield client
    if client.client:
        client.shutdown()
