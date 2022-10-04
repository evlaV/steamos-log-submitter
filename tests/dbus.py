# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus
import xml.etree.ElementTree as et
import pytest
import steamos_log_submitter as sls
import steamos_log_submitter.dbus


class MockDBusBus:
    def __init__(self):
        self.buses = {}

    def get_object(self, bus_name, object_path):
        try:
            bus = self.buses[bus_name]
            return bus['path'][object_path]
        except KeyError:
            raise MockDBusException('org.freedesktop.DBus.Error.ServiceUnknown')

    def add_bus(self, bus_name):
        if bus_name not in self.buses:
            self.buses[bus_name] = {
                'path': {},
                'children': {}
            }

    def add_object(self, bus_name, object_path, obj):
        assert object_path[0] == '/'
        split = object_path.rsplit('/', 1)
        
        self.add_bus(bus_name)
        bus = self.buses[bus_name]
        bus['path'][object_path] = obj

        if split[0] in bus['path']:
            if split[0] not in bus['children']:
                bus['children'][split[0]] = {}
            parent = bus['children'][split[0]]
            parent[split[1]] = obj


class MockDBusObject:
    def __init__(self, bus_name, object_path, bus):
        self.bus_name = bus_name
        self.object_path = object_path
        self.bus = bus
        bus.add_object(bus_name, object_path, self)

        self.properties = {}

    def Introspect(self):
        root = et.Element('node')

        children = self.bus.buses[self.bus_name]['children'].get(self.object_path, {})
        for name in children.keys():
            node = et.Element('node')
            node.attrib['name'] = name
            root.append(node)

        return et.tostring(root)


class MockDBusPropertiesInterface:
    @staticmethod
    def Get(obj, iface, prop):
        try:
            return obj.properties[iface][prop]
        except KeyError as e:
            raise MockDBusException('org.freedesktop.DBus.Error.InvalidArgs') from e


class MockDBusInterface:
    INTERFACES = {'org.freedesktop.DBus.Properties': MockDBusPropertiesInterface}

    def __init__(self, obj, iface):
        self.iface = iface
        self.object = obj

    def __getattr__(self, attr):
        return lambda *args, **kwargs: getattr(self.INTERFACES[self.iface], attr)(self.object, *args, **kwargs)


class MockDBusException(dbus.exceptions.DBusException):
    def __init__(self, name):
        self.name = name

    def get_dbus_name(self):
        return self.name


@pytest.fixture
def mock_dbus(monkeypatch):
    bus = MockDBusBus()
    monkeypatch.setattr(dbus, 'SystemBus', lambda: bus)
    monkeypatch.setattr(dbus, 'Interface', MockDBusInterface)

    return bus
