# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import dbus_next as dbus
import inspect
import pytest
import steamos_log_submitter as sls
import steamos_log_submitter.dbus
from collections.abc import Mapping, Sequence
from typing import Union
from . import count_hits  # NOQA: F401
from .dbus import mock_dbus, MockDBusInterface, MockDBusObject, MockDBusProperties  # NOQA: F401


def test_signature_type():
    assert sls.dbus.signature(int) == 'i'
    assert sls.dbus.signature(float) == 'd'
    assert sls.dbus.signature(bool) == 'b'
    assert sls.dbus.signature(str) == 's'
    assert sls.dbus.signature(list[int]) == 'ai'
    assert sls.dbus.signature(tuple[int]) == '(i)'
    assert sls.dbus.signature(tuple[int, int]) == '(ii)'
    assert sls.dbus.signature(tuple[tuple[int, int], int]) == '((ii)i)'
    assert sls.dbus.signature(Sequence[int]) == 'ai'
    assert sls.dbus.signature(Sequence[Sequence[int]]) == 'aai'
    assert sls.dbus.signature(dict[int, int]) == 'a{ii}'
    assert sls.dbus.signature(Mapping[int, int]) == 'a{ii}'
    assert sls.dbus.signature(Union[int, str]) == 'v'
    assert sls.dbus.signature(int | str) == 'v'

    try:
        sls.dbus.signature(1)
        assert False
    except TypeError:
        pass

    try:
        sls.dbus.signature(None)
        assert False
    except TypeError:
        pass


def test_fn_signature_type():
    def fn__i(self) -> int:
        pass

    def fn_i_(self, a: int):
        pass

    def fn_ai_ai(self, a: Sequence[int]) -> list[int]:
        pass

    async def afn_ai_ai(self, a: Sequence[int]) -> list[int]:
        pass

    assert sls.dbus.fn_signature(fn__i) == inspect.Signature([
        inspect.Parameter('self', inspect._ParameterKind.POSITIONAL_ONLY)
    ], return_annotation='i')
    assert sls.dbus.fn_signature(fn_i_) == inspect.Signature([
        inspect.Parameter('self', inspect._ParameterKind.POSITIONAL_ONLY),
        inspect.Parameter('a', inspect._ParameterKind.POSITIONAL_OR_KEYWORD, annotation='i'),
    ])
    assert sls.dbus.fn_signature(fn_ai_ai) == inspect.Signature([
        inspect.Parameter('self', inspect._ParameterKind.POSITIONAL_ONLY),
        inspect.Parameter('a', inspect._ParameterKind.POSITIONAL_OR_KEYWORD, annotation='ai'),
    ], return_annotation='ai')
    assert sls.dbus.fn_signature(afn_ai_ai) == inspect.Signature([
        inspect.Parameter('self', inspect._ParameterKind.POSITIONAL_ONLY),
        inspect.Parameter('a', inspect._ParameterKind.POSITIONAL_OR_KEYWORD, annotation='ai'),
    ], return_annotation='ai')


@pytest.mark.asyncio
async def test_dbusify():
    @sls.dbus.dbusify
    def fn__i(self) -> int:
        return 1

    @sls.dbus.dbusify
    def fn_i_(self, a: int):
        pass

    @sls.dbus.dbusify
    def fn_ai_ai(self, a: Sequence[int]) -> list[int]:
        return list(a)

    @sls.dbus.dbusify
    async def afn_ai_ai(self, a: Sequence[int]) -> list[int]:
        return list(a)

    assert inspect.signature(fn__i) == inspect.Signature([
        inspect.Parameter('self', inspect._ParameterKind.POSITIONAL_ONLY)
    ], return_annotation='i')
    assert inspect.signature(fn_i_) == inspect.Signature([
        inspect.Parameter('self', inspect._ParameterKind.POSITIONAL_ONLY),
        inspect.Parameter('a', inspect._ParameterKind.POSITIONAL_OR_KEYWORD, annotation='i'),
    ])
    assert inspect.signature(fn_ai_ai) == inspect.Signature([
        inspect.Parameter('self', inspect._ParameterKind.POSITIONAL_ONLY),
        inspect.Parameter('a', inspect._ParameterKind.POSITIONAL_OR_KEYWORD, annotation='ai'),
    ], return_annotation='ai')
    assert inspect.signature(afn_ai_ai) == inspect.Signature([
        inspect.Parameter('self', inspect._ParameterKind.POSITIONAL_ONLY),
        inspect.Parameter('a', inspect._ParameterKind.POSITIONAL_OR_KEYWORD, annotation='ai'),
    ], return_annotation='ai')

    assert fn__i(None) == 1
    fn_i_(None, 0)
    assert fn_ai_ai(None, (2,)) == [2]
    assert await afn_ai_ai(None, (2,)) == [2]


@pytest.mark.asyncio
async def test_invalid_object(mock_dbus):
    await sls.dbus.connect()
    obj = sls.dbus.DBusObject('org.none', '/')
    try:
        await obj._connect()
        assert False
    except dbus.errors.DBusError as e:
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
async def test_property_signaling(mock_dbus, count_hits):
    mock_obj = MockDBusObject('com.valvesoftware', '/charging', mock_dbus)
    mock_obj.properties['com.valvesoftware.Props'] = {
        'Value': 0,
    }
    mock_props = MockDBusProperties(mock_obj, 'com.valvesoftware.Props')
    iface = mock_obj.get_interface('org.freedesktop.DBus.Properties')
    obj = sls.dbus.DBusObject('com.valvesoftware', '/charging')
    props = obj.properties('com.valvesoftware.Props')
    assert await props['Value'] == 0
    assert await mock_props['Value'] == 0

    async def test_full(iface, prop, value):
        assert iface == 'com.valvesoftware.Props'
        assert prop == 'Value'
        assert value == 1
        count_hits()

    await props.subscribe('Value', test_full)
    iface.signal_invalid = False
    mock_props['Value'] = 1
    await asyncio.sleep(0)
    iface.signal_invalid = True
    mock_props['Value'] = 1
    await asyncio.sleep(0)
    assert count_hits.hits == 2
