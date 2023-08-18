# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import os
import pytest
import time
import steamos_log_submitter as sls
import steamos_log_submitter.daemon
from . import patch_module  # NOQA: F401
from .dbus import MockDBusObject
from .dbus import mock_dbus  # NOQA: F401


@pytest.fixture
def fake_socket(monkeypatch):
    prefix = int((time.time() % 1) * 0x400000)
    fakesocket = f'{prefix:06x}.socket'
    monkeypatch.setattr(sls.daemon, 'socket', fakesocket)

    try:
        yield fakesocket
    finally:
        if os.access(fakesocket, os.F_OK):
            os.unlink(fakesocket)


@pytest.fixture
def systemd_object(mock_dbus):
    MockDBusObject('org.freedesktop.systemd1', '/org/freedesktop/systemd1/unit/suspend_2etarget', mock_dbus)


@pytest.fixture
async def dbus_daemon(fake_socket, real_dbus):
    bus = await real_dbus
    daemon = sls.daemon.Daemon()
    await daemon.start()
    return daemon, bus


@pytest.fixture
async def dbus_client(dbus_daemon):
    daemon, bus = await dbus_daemon
    client = sls.client.Client(bus=bus)
    return daemon, client
