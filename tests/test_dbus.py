# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter as sls
import steamos_log_submitter.dbus
from .dbus import mock_dbus, MockDBusObject
import dbus


def test_invalid_object(mock_dbus):
    try:
        sls.dbus.DBusObject('org.none', '/', mock_dbus)
        assert False
    except dbus.exceptions.DBusException as e:
        assert e.get_dbus_name() == 'org.freedesktop.DBus.Error.ServiceUnknown'


def test_valid_object(mock_dbus):
    MockDBusObject('com.valvesoftware', '/', mock_dbus)
    sls.dbus.DBusObject('com.valvesoftware', '/', mock_dbus)


def test_children_object(mock_dbus):
    MockDBusObject('com.valvesoftware', '/a', mock_dbus)
    MockDBusObject('com.valvesoftware', '/a/b', mock_dbus)
    obj = sls.dbus.DBusObject('com.valvesoftware', '/a', mock_dbus)
    assert obj.list_children() == ['/a/b']


def test_object_properties(mock_dbus):
    mock_obj = MockDBusObject('com.valvesoftware', '/gordon', mock_dbus)
    mock_obj.properties['com.valvesoftware.Props'] = {
        'Name': 'Gordon Freeman',
        'Passport': False
    }
    obj = sls.dbus.DBusObject('com.valvesoftware', '/gordon', mock_dbus)
    props = obj.properties('com.valvesoftware.Props')
    assert props['Name'] == 'Gordon Freeman'
    assert not props['Passport']
    try:
        assert not props['G-Man']
    except KeyError:
        pass


def test_no_recursive_children_object(mock_dbus):
    MockDBusObject('com.valvesoftware', '/a', mock_dbus)
    MockDBusObject('com.valvesoftware', '/a/b', mock_dbus)
    MockDBusObject('com.valvesoftware', '/a/b/c', mock_dbus)
    obj = sls.dbus.DBusObject('com.valvesoftware', '/a', mock_dbus)
    assert obj.list_children() == ['/a/b']
    obj = sls.dbus.DBusObject('com.valvesoftware', '/a/b', mock_dbus)
    assert obj.list_children() == ['/a/b/c']
    obj = sls.dbus.DBusObject('com.valvesoftware', '/a/b/c', mock_dbus)
    assert obj.list_children() == []
