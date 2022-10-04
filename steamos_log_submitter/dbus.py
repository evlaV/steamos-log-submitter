# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus
import xml.etree.ElementTree as et

system_bus = dbus.SystemBus()


class DBusObject:
    def __init__(self, bus_name, object_path, bus=system_bus):
        self.bus = bus
        self.bus_name = bus_name
        self.object_path = object_path
        self.object = bus.get_object(bus_name, object_path)

    def properties(self, iface):
        return DBusProperties(self.object, iface)

    def list_children(self):
        root = et.fromstring(self.object.Introspect())
        return [f'{self.object_path}/' + node.attrib['name'] for node in root.findall('node')]


class DBusProperties:
    def __init__(self, obj, iface):
        self._properties_iface = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')
        self.iface = iface

    def __getitem__(self, name):
        try:
            return self._properties_iface.Get(self.iface, name)
        except dbus.exceptions.DBusException as e:
            if e.get_dbus_name() == 'org.freedesktop.DBus.Error.InvalidArgs':
                raise KeyError(e.get_dbus_message()) from e
            raise
