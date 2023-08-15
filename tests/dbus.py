# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import collections
import dbus_next as dbus
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
            raise dbus.errors.DBusError('org.freedesktop.DBus.Error.ServiceUnknown', '')

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
            raise dbus.errors.DBusError('org.freedesktop.DBus.Error.ServiceUnknown', '')
        for name in children.keys():
            node = et.Element('node')
            node.attrib['name'] = name
            root.append(node)

        obj = self.buses[bus_name]['path'][object_path]
        for key, val in obj.interfaces.items():
            iface = et.Element('interface')
            iface.attrib['name'] = key
            for name in val._methods.keys():
                method = et.Element('method')
                method.attrib['name'] = name
                iface.append(method)
            root.append(iface)

        return et.tostring(root)

    def get_proxy_object(self, bus_name, object_path, introspection):
        return self.buses[bus_name]['path'][object_path]

    def add_message_handler(self, handler):
        pass

    async def request_name(self, name: str):
        pass

    def export(self, path: str, iface):
        pass


class MockDBusProperties:
    def __init__(self, obj, iface):
        try:
            self.properties = obj.properties[iface]
        except KeyError:
            raise dbus.errors.InterfaceNotFoundError(iface)
        self._iface = iface
        self._obj = obj

    async def __getitem__(self, name):
        if name not in self.properties:
            raise AttributeError(name)
        return self.properties[name]

    def __setitem__(self, name, value):
        properties_iface = self._obj.interfaces['org.freedesktop.DBus.Properties']
        properties_iface.set(self._iface, name, value)


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

    def add_interface(self, iface):
        self.interfaces[iface._iface] = iface


class MockDBusInterface:
    def __init__(self, obj, iface):
        self._methods = {}
        self._iface = iface
        self._object = obj
        self._signals = {}

    def __getattr__(self, attr):
        type, name = attr.split('_', 1)

        async def call(*args, **kwargs):
            method = self._methods[name]
            return method(*args, **kwargs)

        async def get():
            properties_iface = self._object.interfaces['org.freedesktop.DBus.Properties']
            return properties_iface.get(self._iface, name)

        def on(cb):
            self._signals[name] = self._signals.get(name, [])
            self._signals[name].append(cb)

        if type == 'call':
            return call
        if type == 'get':
            return get
        if type == 'on':
            return on

    def signal(self, signal, *args):
        name = dbus.proxy_object.BaseProxyInterface._to_snake_case(signal)
        if name in self._signals:
            for cb in self._signals[name]:
                cb(*args)


class MockDBusPropertiesInterface(MockDBusInterface):
    def __init__(self, obj):
        super().__init__(obj, 'org.freedesktop.DBus.Properties')
        self._methods['get'] = self.get
        self._methods['set'] = self.set
        self.signal_invalid = False

    def get(self, iface, name):
        return MockDBusVariant(self._object.properties[iface][name])

    def set(self, iface, name, value):
        self._object.properties[iface][name] = value
        if self.signal_invalid:
            self.signal('PropertiesChanged', iface, {}, [name])
        else:
            self.signal('PropertiesChanged', iface, {name: MockDBusVariant(value)}, [])


class MockDBusVariant:
    def __init__(self, value):
        self.value = value


@pytest.fixture
def mock_dbus(monkeypatch):
    bus = MockDBusBus()
    monkeypatch.setattr(dbus.aio, 'MessageBus', lambda bus_type: bus)
    monkeypatch.setattr(sls.dbus, 'system_bus', bus)
    monkeypatch.setattr(sls.dbus, 'connected', True)
    return bus


@pytest.fixture
async def real_dbus(monkeypatch):
    monkeypatch.setattr(dbus, 'BusType', collections.namedtuple('BusType', ['SYSTEM', 'SESSION'])(dbus.BusType.SESSION, dbus.BusType.SESSION))
    sls.dbus.connected = False
    await sls.dbus.connect()
    return sls.dbus.system_bus.unique_name
