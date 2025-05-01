# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter as sls
import steamos_log_submitter.daemon
from . import patch_module  # NOQA: F401
from .dbus import mock_dbus  # NOQA: F401
from .dbus import real_dbus


async def dbus_daemon(monkeypatch):
    bus = await real_dbus(monkeypatch)
    daemon = sls.daemon.Daemon()
    await daemon.start()
    return daemon, bus


async def dbus_client(monkeypatch):
    daemon, bus = await dbus_daemon(monkeypatch)
    client = sls.client.Client(bus=bus)
    return daemon, client
