# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import pytest
import steamos_log_submitter as sls
import steamos_log_submitter.daemon
from . import patch_module  # NOQA: F401
from .dbus import mock_dbus  # NOQA: F401


@pytest.fixture
async def dbus_daemon(real_dbus):
    bus = await real_dbus
    daemon = sls.daemon.Daemon()
    await daemon.start()
    return daemon, bus


@pytest.fixture
async def dbus_client(dbus_daemon):
    daemon, bus = await dbus_daemon
    client = sls.client.Client(bus=bus)
    return daemon, client
