# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next
import pytest
import steamos_log_submitter as sls
import steamos_log_submitter.dbus
import xml.etree.ElementTree as et


class MockDBusBus:
    def __init__(self):
        self.buses = {}

    async def connect(self):
        pass

    def get_object(self, bus_name, object_path):
        try:
            bus = self.buses[bus_name]
            return bus['path'][object_path]
        except KeyError:
            raise dbus_next.errors.DBusError('org.freedesktop.DBus.Error.ServiceUnknown', '')

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
            bus['path'][split[0]].child_paths.append(object_path)

    async def introspect(self, bus_name, object_path):
        root = et.Element('node')

        try:
            children = self.buses[bus_name]['children'].get(object_path, {})
        except KeyError:
            raise dbus_next.errors.DBusError('org.freedesktop.DBus.Error.ServiceUnknown', '')
        for name in children.keys():
            node = et.Element('node')
            node.attrib['name'] = name
            root.append(node)

        return et.tostring(root)

    def get_proxy_object(self, bus_name, object_path, introspection):
        return self.buses[bus_name]['path'][object_path]


class MockDBusProperties:
    def __init__(self, obj, iface):
        try:
            self.properties = obj.properties[iface]
        except KeyError:
            raise dbus_next.errors.InterfaceNotFoundError(iface)
        self._iface = iface

    async def __getitem__(self, name):
        if name not in self.properties:
            raise AttributeError(name)


class MockDBusObject:
    def __init__(self, bus_name, object_path, bus):
        self.bus_name = bus_name
        self.object_path = object_path
        self.bus = bus
        self.child_paths = []
        bus.add_object(bus_name, object_path, self)

        self.properties = {}
        self.interfaces = {'org.freedesktop.DBus.Properties': MockDBusPropertiesInterface(self)}

    def get_interface(self, iface):
        return self.interfaces[iface]


class MockDBusInterface:
    methods = {}

    def __init__(self, obj, iface):
        self.iface = iface
        self.object = obj

    @classmethod
    def method(cls, fn):
        name = dbus_next.proxy_object.BaseProxyInterface._to_snake_case(fn.__name__)
        cls.methods[name] = fn
        return fn

    def __getattr__(self, attr):
        type, name = attr.split('_', 1)

        async def call(*args, **kwargs):
            method = self.methods[name]
            return method(self, *args, **kwargs)

        async def get():
            properties_iface = self.object.interfaces['org.freedesktop.DBus.Properties']
            return properties_iface.get(self.iface, name)

        if type == 'call':
            return call
        if type == 'get':
            return get


class MockDBusPropertiesInterface(MockDBusInterface):
    def __init__(self, obj):
        super().__init__(obj, 'org.freedesktop.DBus.Properties')
        self.methods['Get'] = self.get

    @MockDBusInterface.method
    def get(self, iface, name):
        return MockDBusVariant(self.object.properties[iface][name])


class MockDBusVariant:
    def __init__(self, value):
        self.value = value


@pytest.fixture
def mock_dbus(monkeypatch):
    bus = MockDBusBus()
    monkeypatch.setattr(dbus_next.aio, 'MessageBus', lambda bus_type: bus)
    monkeypatch.setattr(sls.dbus, 'system_bus', bus)
    return bus
