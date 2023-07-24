# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import dbus_next
import pytest
import steamos_log_submitter as sls
import steamos_log_submitter.dbus
from . import count_hits  # NOQA: F401
from .dbus import mock_dbus, MockDBusInterface, MockDBusObject, MockDBusProperties  # NOQA: F401


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


@pytest.mark.asyncio
async def test_interface(mock_dbus, count_hits):
    mock_obj = MockDBusObject('com.valvesoftware', '/crowbar', mock_dbus)

    class TestDBusInterface(MockDBusInterface):
        def __init__(self, obj):
            super().__init__(self, 'com.valvesoftware.Crowbar')
            self._methods['swing'] = self.swing

        def swing(self):
            count_hits()

    mock_iface = TestDBusInterface(mock_obj)
    mock_obj.add_interface(mock_iface)

    obj = sls.dbus.DBusObject('com.valvesoftware', '/crowbar')
    iface = await obj.interface('com.valvesoftware.Crowbar')
    print(iface)
    await iface.swing()
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_property_signaling(mock_dbus):
    mock_obj = MockDBusObject('com.valvesoftware', '/charging', mock_dbus)
    mock_obj.properties['com.valvesoftware.Props'] = {
        'Value': 0,
    }
    mock_props = MockDBusProperties(mock_obj, 'com.valvesoftware.Props')
    obj = sls.dbus.DBusObject('com.valvesoftware', '/charging')
    props = obj.properties('com.valvesoftware.Props')
    assert await props['Value'] == 0
    assert await mock_props['Value'] == 0
    hit = False

    async def test_full(iface, prop, value):
        nonlocal hit
        assert iface == 'com.valvesoftware.Props'
        assert prop == 'Value'
        assert value == 1
        hit = True

    await props.subscribe('Value', test_full)
    mock_props['Value'] = 1
    await asyncio.sleep(0)
    assert hit
