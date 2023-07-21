# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next
import pytest
import steamos_log_submitter as sls
import steamos_log_submitter.dbus
from .dbus import mock_dbus, MockDBusObject  # NOQA: F401


@pytest.mark.asyncio
async def test_invalid_object(mock_dbus):
    await sls.dbus.connect()
    obj = sls.dbus.DBusObject('org.none', '/')
    try:
        await obj._connect()
        assert False
    except dbus_next.errors.DBusError as e:
        assert e.type == 'org.freedesktop.DBus.Error.ServiceUnknown'


@pytest.mark.asyncio
async def test_valid_object(mock_dbus):
    MockDBusObject('com.valvesoftware', '/', mock_dbus)
    obj = sls.dbus.DBusObject('com.valvesoftware', '/')
    await obj._connect()


@pytest.mark.asyncio
async def test_children_object(mock_dbus):
    MockDBusObject('com.valvesoftware', '/a', mock_dbus)
    MockDBusObject('com.valvesoftware', '/a/b', mock_dbus)
    obj = sls.dbus.DBusObject('com.valvesoftware', '/a')
    assert await obj.list_children() == ['/a/b']


@pytest.mark.asyncio
async def test_object_properties(mock_dbus):
    mock_obj = MockDBusObject('com.valvesoftware', '/gordon', mock_dbus)
    mock_obj.properties['com.valvesoftware.Props'] = {
        'Name': 'Gordon Freeman',
        'Passport': False
    }
    obj = sls.dbus.DBusObject('com.valvesoftware', '/gordon')
    props = obj.properties('com.valvesoftware.Props')
    assert await props['Name'] == 'Gordon Freeman'
    assert not await props['Passport']
    try:
        assert not await props['G-Man']
    except KeyError:
        pass


@pytest.mark.asyncio
async def test_no_recursive_children_object(mock_dbus):
    MockDBusObject('com.valvesoftware', '/a', mock_dbus)
    MockDBusObject('com.valvesoftware', '/a/b', mock_dbus)
    MockDBusObject('com.valvesoftware', '/a/b/c', mock_dbus)
    obj = sls.dbus.DBusObject('com.valvesoftware', '/a')
    assert await obj.list_children() == ['/a/b']
    obj = sls.dbus.DBusObject('com.valvesoftware', '/a/b')
    assert await obj.list_children() == ['/a/b/c']
    obj = sls.dbus.DBusObject('com.valvesoftware', '/a/b/c')
    assert await obj.list_children() == []
