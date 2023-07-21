# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next

connected = False
system_bus = None


async def connect():
    global system_bus
    global connected
    if connected:
        return

    system_bus = dbus_next.aio.MessageBus(bus_type=dbus_next.BusType.SYSTEM)

    await system_bus.connect()
    connected = True


class DBusProperties:
    def __init__(self, obj, iface):
        self._properties_iface = None
        self.obj = obj
        self.iface = iface

    async def __getitem__(self, name):
        if not self._properties_iface:
            if not self.obj.object:
                await self.obj._connect()
            self._properties_iface = self.obj.object.get_interface('org.freedesktop.DBus.Properties')
        try:
            variant = await self._properties_iface.call_get(self.iface, name)
            return variant.value
        except OSError:
            raise


class DBusObject:
    def __init__(self, bus_name: str, object_path: str):
        self.bus = system_bus
        self.bus_name = bus_name
        self.object_path = object_path
        self.object = None

    async def _connect(self):
        if self.object:
            return
        if not connected:
            await connect()
        if not self.bus:
            self.bus = system_bus
        introspection = await self.bus.introspect(self.bus_name, self.object_path)
        self.object = self.bus.get_proxy_object(self.bus_name, self.object_path, introspection)

    def properties(self, iface: str) -> DBusProperties:
        return DBusProperties(self, iface)

    async def list_children(self):
        await self._connect()
        return self.object.child_paths
