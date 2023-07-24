# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import dbus_next

connected = False
system_bus = None


async def connect():  # pragma: no cover
    global system_bus
    global connected
    if connected:
        return

    system_bus = dbus_next.aio.MessageBus(bus_type=dbus_next.BusType.SYSTEM)

    await system_bus.connect()
    connected = True


class DBusInterface:
    def __init__(self, obj, iface):
        self._obj = obj
        self._iface = iface
        self._iface_handle = None

    def __getattr__(self, name):
        async def call(*args, **kwargs):
            if not self._iface_handle:
                if not self._obj.object:
                    await self._obj._connect()
                self._iface_handle = self._obj.object.get_interface(self._iface)
            method = getattr(self._iface_handle, f'call_{name}')
            setattr(self, name, method)  # Memoize the method so we only have to look it up once
            return await method(*args, **kwargs)
        return call


class DBusProperties:
    def __init__(self, obj, iface):
        self._properties_iface = None
        self._obj = obj
        self._iface = iface
        self._subscribed = {}

    async def __getitem__(self, name):
        if not self._properties_iface:
            if not self._obj.object:
                await self._obj._connect()
            self._properties_iface = self._obj.object.get_interface('org.freedesktop.DBus.Properties')
        try:
            variant = await self._properties_iface.call_get(self._iface, name)
            return variant.value
        except OSError:
            raise

    def _update_props(self, iface: str, changed: dict[str, dbus_next.Variant], invalidated: list[str]):
        async def do_cb(cb, iface: str, prop: str, value):
            if value is None:
                value = await self._properties_iface.call_get(self._iface, prop)
            else:
                value = value.value
            await cb(iface, prop, value)

        for prop, value in changed.items():
            if prop not in self._subscribed:
                continue
            for handler in self._subscribed[prop]:
                asyncio.create_task(do_cb(handler, iface, prop, value))
        for prop in invalidated:
            if prop not in self._subscribed:
                continue
            for handler in self._subscribed[prop]:
                asyncio.create_task(do_cb(handler, iface, prop, None))

    async def subscribe(self, prop: str, cb):
        if not self._obj.object:
            await self._obj._connect()
        if not self._subscribed:
            iface_handle = self._obj.object.get_interface('org.freedesktop.DBus.Properties')
            iface_handle.on_properties_changed(self._update_props)
        self._subscribed[prop] = self._subscribed.get(prop, [])
        self._subscribed[prop].append(cb)


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

    async def interface(self, iface: str) -> DBusInterface:
        await self._connect()
        return DBusInterface(self, iface)

    async def subscribe(self, iface: str, signal: str, cb):
        await self._connect()
        iface_handle = self.object.get_interface(iface)
        name = dbus_next.proxy_object.BaseProxyInterface._to_snake_case(signal)
        getattr(iface_handle, f'on_{name}')(cb)

    async def list_children(self):
        await self._connect()
        return self.object.child_paths
