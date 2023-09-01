# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import collections
import json
import os
import pytest
import time
import typing
import steamos_log_submitter as sls
from steamos_log_submitter.helpers import create_helper

from .. import always_raise, awaitable, setup_categories, unreachable
from .. import data_directory, fake_async_subprocess, helper_directory, mock_config, open_shim, patch_module  # NOQA: F401
from ..daemon import dbus_daemon  # NOQA: F401
from ..dbus import mock_dbus, real_dbus, MockDBusObject  # NOQA: F401

helper = create_helper('sysinfo')


def make_usb_devs(monkeypatch, devs):
    def read_file(fname):
        dev, node = fname.split('/')[-2:]
        if dev not in devs:
            return None
        return devs[dev].get(node)
    monkeypatch.setattr(helper, 'read_file', read_file)


@pytest.mark.asyncio
async def test_collect_usb_none(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: [])
    monkeypatch.setattr(helper, 'read_file', unreachable)
    devices = await helper.list_usb()
    assert isinstance(devices, list)
    assert not len(devices)


@pytest.mark.asyncio
async def test_collect_usb_nondev(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['usb1'])
    monkeypatch.setattr(helper, 'read_file', unreachable)
    devices = await helper.list_usb()
    assert isinstance(devices, list)
    assert not len(devices)


@pytest.mark.asyncio
async def test_collect_usb_bad_dev(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['1-1'])
    make_usb_devs(monkeypatch, {'1-1': {}})
    devices = await helper.list_usb()
    assert isinstance(devices, list)
    assert not len(devices)


@pytest.mark.asyncio
async def test_collect_usb_vid_pid_only(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['1-1'])
    make_usb_devs(monkeypatch, {'1-1': {
        'idVendor': '1234',
        'idProduct': '5678'
    }})
    devices = await helper.list_usb()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0] == {
        'vid': '1234',
        'pid': '5678'
    }


@pytest.mark.asyncio
async def test_collect_usb_manufacturer(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['1-1'])
    make_usb_devs(monkeypatch, {'1-1': {
        'idVendor': '1234',
        'idProduct': '5678',
        'manufacturer': 'Black Mesa'
    }})
    devices = await helper.list_usb()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0] == {
        'vid': '1234',
        'pid': '5678',
        'manufacturer': 'Black Mesa'
    }


@pytest.mark.asyncio
async def test_collect_usb_product(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['1-1'])
    make_usb_devs(monkeypatch, {'1-1': {
        'idVendor': '1234',
        'idProduct': '5678',
        'product': 'Hazardous Environment Suit'
    }})
    devices = await helper.list_usb()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0] == {
        'vid': '1234',
        'pid': '5678',
        'product': 'Hazardous Environment Suit'
    }


@pytest.mark.asyncio
async def test_collect_usb_all(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['1-1'])
    make_usb_devs(monkeypatch, {'1-1': {
        'idVendor': '1234',
        'idProduct': '5678',
        'manufacturer': 'Black Mesa',
        'product': 'Hazardous Environment Suit'
    }})
    devices = await helper.list_usb()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0] == {
        'vid': '1234',
        'pid': '5678',
        'manufacturer': 'Black Mesa',
        'product': 'Hazardous Environment Suit'
    }


@pytest.mark.asyncio
async def test_collect_bluetooth_no_adapters(monkeypatch, mock_dbus):
    bus = 'org.bluez'
    mock_dbus.add_bus(bus)
    MockDBusObject(bus, '/org/bluez', mock_dbus)

    devices = await helper.list_bluetooth()
    assert isinstance(devices, list)
    assert not len(devices)


@pytest.mark.asyncio
async def test_collect_bluetooth_empty_adapter(monkeypatch, mock_dbus):
    bus = 'org.bluez'
    mock_dbus.add_bus(bus)
    MockDBusObject(bus, '/org/bluez', mock_dbus)
    MockDBusObject(bus, '/org/bluez/hci0', mock_dbus)

    devices = await helper.list_bluetooth()
    assert isinstance(devices, list)
    assert not len(devices)


@pytest.mark.asyncio
async def test_collect_bluetooth_adapter_partial_device(monkeypatch, mock_dbus):
    bus = 'org.bluez'
    mock_dbus.add_bus(bus)
    MockDBusObject(bus, '/org/bluez', mock_dbus)
    MockDBusObject(bus, '/org/bluez/hci0', mock_dbus)
    dev = MockDBusObject(bus, '/org/bluez/hci0/dev_01_02_03_04_05', mock_dbus)
    dev.properties['org.bluez.Device1'] = {
        'Address': '01:02:03:04:05',
        'Name': 'Crowbar'
    }

    devices = await helper.list_bluetooth()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0] == {'address': '01:02:03:04:05', 'name': 'Crowbar', 'adapter': 'hci0'}


@pytest.mark.asyncio
async def test_collect_monitors_none(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: [])
    monkeypatch.setattr(helper, 'read_file', unreachable)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert not len(devices)


@pytest.mark.asyncio
async def test_collect_monitors_other_only(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['version'])
    monkeypatch.setattr(helper, 'read_file', unreachable)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert not len(devices)


@pytest.mark.asyncio
async def test_collect_monitors_card_only(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['card0'])
    monkeypatch.setattr(helper, 'read_file', unreachable)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert not len(devices)


@pytest.mark.asyncio
async def test_collect_monitors_nothing(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', lambda _, binary: None)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert not len(devices)


def fix_edid_checksum(edid):
    checksum = -sum(edid[:127]) & 0xFF
    return edid[:127] + bytes([checksum]) + edid[128:]


@pytest.mark.asyncio
async def test_collect_monitors_edid(monkeypatch):
    edid = fix_edid_checksum(b'''\0\xFF\xFF\xFF\xFF\xFF\xFF\0 \xB6\x23\x01AAAAxx\1\4
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxx\0\0xxxxxxxxxxxxxxxx\0\0\0\xFC\0Gordon's
    \0\0\0\xFE\0And a crowbar\0\0\0\xFF\0MK 5\n        \0''')

    def read_file(fname, binary):
        if fname.endswith('card0-DP-1/edid'):
            assert binary
            return edid
        if fname.endswith('card0-DP-1/modes'):
            assert not binary
            return '1024x768'
        assert False, f'Bad filename {fname}'

    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', read_file)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0]['edid'] == edid.hex()
    assert devices[0]['pnp'] == 'HEV'
    assert devices[0]['pid'] == '0123'
    assert devices[0]['serial'] == '41414141'
    assert devices[0]['version'] == '1.4'
    assert devices[0]['checksum'] is True
    assert devices[0]['desc0'] == {'type': 'unknown'}
    assert devices[0]['desc1'] == {'type': 'name', 'value': 'Gordon\'s'}
    assert devices[0]['desc2'] == {'type': 'text', 'value': 'And a crowbar'}
    assert devices[0]['desc3'] == {'type': 'serial', 'value': 'MK 5'}
    assert devices[0]['modes'] == ['1024x768']


@pytest.mark.asyncio
async def test_collect_monitors_edid_bad_checksum(monkeypatch):
    edid = b'''\0\xFF\xFF\xFF\xFF\xFF\xFF\0 \xB6\x23\x01AAAAxx\1\4
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxx\0\0xxxxxxxxxxxxxxxx\0\0\0\xFC\0Gordon's
    \0\0\0\xFE\0And a crowbar\0\0\0\xFF\0MK 5\n        \0\x4F'''

    def read_file(fname, binary):
        if fname.endswith('card0-DP-1/edid'):
            assert binary
            return edid
        if fname.endswith('card0-DP-1/modes'):
            assert not binary
            return '1024x768'
        assert False, f'Bad filename {fname}'

    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', read_file)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0]['edid'] == edid.hex()
    assert devices[0]['pnp'] == 'HEV'
    assert devices[0]['pid'] == '0123'
    assert devices[0]['serial'] == '41414141'
    assert devices[0]['version'] == '1.4'
    assert devices[0]['checksum'] is False
    assert devices[0]['desc0'] == {'type': 'unknown'}
    assert devices[0]['desc1'] == {'type': 'name', 'value': 'Gordon\'s'}
    assert devices[0]['desc2'] == {'type': 'text', 'value': 'And a crowbar'}
    assert devices[0]['desc3'] == {'type': 'serial', 'value': 'MK 5'}
    assert devices[0]['modes'] == ['1024x768']


@pytest.mark.asyncio
async def test_collect_monitors_edid_short(monkeypatch):
    edid = b'''\0\xFF\xFF\xFF\xFF\xFF\xFF\0 \xB6\x23\x01AAAAxx\1\4'''

    def read_file(fname, binary):
        if fname.endswith('card0-DP-1/edid'):
            assert binary
            return edid
        if fname.endswith('card0-DP-1/modes'):
            assert not binary
            return '1024x768'
        assert False, f'Bad filename {fname}'

    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', read_file)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0]['edid'] == edid.hex()
    assert 'pnp' not in devices[0]
    assert 'pid' not in devices[0]
    assert 'serial' not in devices[0]
    assert 'version' not in devices[0]
    assert 'desc0' not in devices[0]
    assert 'desc1' not in devices[0]
    assert 'desc2' not in devices[0]
    assert 'desc3' not in devices[0]
    assert devices[0]['modes'] == ['1024x768']


@pytest.mark.asyncio
async def test_collect_monitors_edid_ignore_timing_desc(monkeypatch):
    edid = fix_edid_checksum(b'''\0\xFF\xFF\xFF\xFF\xFF\xFF\0 \xB6\x23\x01AAAAxx\1\4
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxx\1\0xxxxxxxxxxxxxxxx\2\0\0\xFC\0Gordon's
    \0\1\0\xFE\0And a crowbar\0\2\0\xFF\0MK 5\n        \0''')

    def read_file(fname, binary):
        if fname.endswith('card0-DP-1/edid'):
            assert binary
            return edid
        if fname.endswith('card0-DP-1/modes'):
            assert not binary
            return '1024x768'
        assert False, f'Bad filename {fname}'

    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', read_file)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0]['edid'] == edid.hex()
    assert devices[0]['pnp'] == 'HEV'
    assert devices[0]['pid'] == '0123'
    assert devices[0]['serial'] == '41414141'
    assert devices[0]['version'] == '1.4'
    assert devices[0]['checksum'] is True
    assert 'desc0' not in devices[0]
    assert 'desc1' not in devices[0]
    assert 'desc2' not in devices[0]
    assert 'desc3' not in devices[0]
    assert devices[0]['modes'] == ['1024x768']


@pytest.mark.asyncio
async def test_collect_monitors_edid_bad_magic(monkeypatch):
    edid = fix_edid_checksum(b'''\1\xFF\xFF\xFF\xFF\xFF\xFF\0 \xB6\x23\x01AAAAxx\1\4
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxx\0\0xxxxxxxxxxxxxxxx\0\0\0\xFC\0Gordon's
    \0\0\0\xFE\0And a crowbar\0\0\0\xFF\0MK 5\n        \0''')

    def read_file(fname, binary):
        if fname.endswith('card0-DP-1/edid'):
            assert binary
            return edid
        if fname.endswith('card0-DP-1/modes'):
            assert not binary
            return '1024x768'
        assert False, f'Bad filename {fname}'

    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', read_file)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0]['edid'] == edid.hex()
    assert 'pnp' not in devices[0]
    assert 'pid' not in devices[0]
    assert 'serial' not in devices[0]
    assert 'version' not in devices[0]
    assert 'desc0' not in devices[0]
    assert 'desc1' not in devices[0]
    assert 'desc2' not in devices[0]
    assert 'desc3' not in devices[0]
    assert devices[0]['modes'] == ['1024x768']


@pytest.mark.asyncio
async def test_collect_monitors_edid_no_modes(monkeypatch):
    edid = fix_edid_checksum(b'''\0\xFF\xFF\xFF\xFF\xFF\xFF\0 \xB6\x23\x01AAAAxx\1\4
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxx\0\0xxxxxxxxxxxxxxxx\0\0\0\xFC\0Gordon's
    \0\0\0\xFE\0And a crowbar\0\0\0\xFF\0MK 5\n        \0''')

    def read_file(fname, binary):
        if fname.endswith('card0-DP-1/edid'):
            assert binary
            return edid
        if fname.endswith('card0-DP-1/modes'):
            assert not binary
            return None
        assert False, f'Bad filename {fname}'

    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', read_file)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0]['edid'] == edid.hex()
    assert devices[0]['pnp'] == 'HEV'
    assert devices[0]['pid'] == '0123'
    assert devices[0]['serial'] == '41414141'
    assert devices[0]['version'] == '1.4'
    assert devices[0]['checksum'] is True
    assert devices[0]['desc0'] == {'type': 'unknown'}
    assert devices[0]['desc1'] == {'type': 'name', 'value': 'Gordon\'s'}
    assert devices[0]['desc2'] == {'type': 'text', 'value': 'And a crowbar'}
    assert devices[0]['desc3'] == {'type': 'serial', 'value': 'MK 5'}
    assert 'modes' not in devices[0]


@pytest.mark.asyncio
async def test_collect_filesystems_raise(monkeypatch):
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', always_raise(OSError))
    assert await helper.list('filesystems') is None


@pytest.mark.asyncio
async def test_collect_filesystems_malformed(fake_async_subprocess):
    fake_async_subprocess(stdout=b'!')
    assert await helper.list('filesystems') is None


@pytest.mark.asyncio
async def test_collect_filesystems_missing(fake_async_subprocess):
    fake_async_subprocess(stdout=b'{"wrong_things":"go_here"}')
    assert await helper.list_filesystems() is None


@pytest.mark.asyncio
async def test_collect_filesystems_get_missing_size(fake_async_subprocess, mock_dbus):
    blob = json.dumps({'filesystems': [{'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'bitbucket', 'size': None}]})
    fake_async_subprocess(stdout=blob.encode())
    bus = 'org.freedesktop.UDisks2'
    mock_dbus.add_bus(bus)
    block_dev = MockDBusObject(bus, '/org/freedesktop/UDisks2/block_devices/null', mock_dbus)
    block_dev.properties['org.freedesktop.UDisks2.Block'] = {
        'Size': 0,
    }

    fs = await helper.list_filesystems()
    assert fs == [{'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'bitbucket', 'size': 0}]


@pytest.mark.asyncio
async def test_collect_filesystems_unknown_missing_size(fake_async_subprocess, mock_dbus):
    blob = json.dumps({'filesystems': [{'uuid': None, 'source': 'resonance', 'target': '/', 'fstype': 'cascade', 'size': None}]})
    fake_async_subprocess(stdout=blob.encode())
    bus = 'org.freedesktop.UDisks2'
    mock_dbus.add_bus(bus)

    fs = await helper.list_filesystems()
    assert fs == [{'uuid': None, 'source': 'resonance', 'target': '/', 'fstype': 'cascade', 'size': None}]


@pytest.mark.asyncio
async def test_collect_filesystems_filter(fake_async_subprocess):
    blob = json.dumps({'filesystems': [
        {'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'bitbucket', 'size': 0},
        {'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'fuse.ntfs-3g', 'size': 0},
        {'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'fuse.portal', 'size': 0},
        {'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'fuse.hl2.AppImage', 'size': 0},
    ]})
    fake_async_subprocess(stdout=blob.encode())
    fs = await helper.list_filesystems()
    assert fs == [
        {'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'bitbucket', 'size': 0},
        {'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'fuse.ntfs-3g', 'size': 0},
    ]


@pytest.mark.asyncio
async def test_collect_filesystems_clean(fake_async_subprocess):
    blob = json.dumps({'filesystems': [{'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'bitbucket', 'size': 0}]})
    fake_async_subprocess(stdout=blob.encode())
    fs = await helper.list_filesystems()
    assert fs == [{'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'bitbucket', 'size': 0}]


@pytest.mark.asyncio
async def test_collect_system(monkeypatch):
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_build_id', lambda: '20230704')
    monkeypatch.setattr(os, 'access', lambda x, y: True)
    monkeypatch.setattr(helper, 'get_vram', awaitable(lambda: '1024 MB'))
    monkeypatch.setattr(helper, 'get_ram', awaitable(lambda: ('14400000 kB', '1024000 kB')))

    assert dict(await helper.list_system()) == {
        'branch': 'main',
        'release': '20230704',
        'devmode': True,
        'vram': '1024 MB',
        'mem': '14400000 kB',
        'swap': '1024000 kB',
    }


@pytest.mark.asyncio
async def test_collect_system_no_vram(monkeypatch):
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_build_id', lambda: '20230704')
    monkeypatch.setattr(os, 'access', lambda x, y: True)
    monkeypatch.setattr(helper, 'get_vram', awaitable(lambda: None))
    monkeypatch.setattr(helper, 'get_ram', awaitable(lambda: ('14400000 kB', '1024000 kB')))

    assert dict(await helper.list_system()) == {
        'branch': 'main',
        'release': '20230704',
        'devmode': True,
        'mem': '14400000 kB',
        'swap': '1024000 kB',
    }


@pytest.mark.asyncio
async def test_collect_system_no_mem(monkeypatch):
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_build_id', lambda: '20230704')
    monkeypatch.setattr(os, 'access', lambda x, y: True)
    monkeypatch.setattr(helper, 'get_vram', awaitable(lambda: '1024 MB'))
    monkeypatch.setattr(helper, 'get_ram', awaitable(lambda: (None, '1024000 kB')))

    assert dict(await helper.list_system()) == {
        'branch': 'main',
        'release': '20230704',
        'devmode': True,
        'vram': '1024 MB',
        'swap': '1024000 kB',
    }


@pytest.mark.asyncio
async def test_collect_system_no_swap(monkeypatch):
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_build_id', lambda: '20230704')
    monkeypatch.setattr(os, 'access', lambda x, y: True)
    monkeypatch.setattr(helper, 'get_vram', awaitable(lambda: '1024 MB'))
    monkeypatch.setattr(helper, 'get_ram', awaitable(lambda: ('14400000 kB', None)))

    assert dict(await helper.list_system()) == {
        'branch': 'main',
        'release': '20230704',
        'devmode': True,
        'vram': '1024 MB',
        'mem': '14400000 kB',
    }


@pytest.mark.asyncio
async def test_collect_batteries_none(monkeypatch, mock_dbus):
    bus = 'org.freedesktop.UPower'
    mock_dbus.add_bus(bus)
    MockDBusObject(bus, '/org/freedesktop/UPower/devices', mock_dbus)

    devices = await helper.list_batteries()
    assert isinstance(devices, list)
    assert not len(devices)


@pytest.mark.asyncio
async def test_collect_batteries_some(monkeypatch, mock_dbus):
    bus = 'org.freedesktop.UPower'
    mock_dbus.add_bus(bus)
    MockDBusObject(bus, '/org/freedesktop/UPower/devices', mock_dbus)
    dev = MockDBusObject(bus, '/org/freedesktop/UPower/devices/battery_BAT1', mock_dbus)
    dev.properties['org.freedesktop.UPower.Device'] = {
        'EnergyFull': 99.8,
        'EnergyFullDesign': 99.9,
        'Model': 'PbAcid',
        'NativePath': 'BAT1',
        'Online': False,
        'State': 1,
        'Type': 5,
    }

    devices = await helper.list_batteries()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0] == {
        'energy_full': 99.8,
        'energy_full_design': 99.9,
        'model': 'PbAcid',
        'native_path': 'BAT1',
        'online': False,
        'type': 5
    }


@pytest.mark.asyncio
async def test_collect(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', ['usb'])
    monkeypatch.setattr(helper, 'list_usb', awaitable(lambda: []))

    assert not await helper.collect()
    with open(f'{data_directory}/sysinfo-pending.json') as f:
        output = json.load(f)
    assert output == {'usb': []}


@pytest.mark.asyncio
async def test_collect_skip(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', ['usb'])
    monkeypatch.setattr(helper, 'list_usb', awaitable(always_raise(RuntimeError)))

    assert not await helper.collect()
    with open(f'{data_directory}/sysinfo-pending.json') as f:
        output = json.load(f)
    assert output == {}


@pytest.mark.asyncio
async def test_collect_malformed(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', ['usb'])
    monkeypatch.setattr(helper, 'list_usb', awaitable(lambda: []))

    with open(f'{data_directory}/sysinfo-pending.json', 'w') as f:
        f.write('not json')

    assert not await helper.collect()
    with open(f'{data_directory}/sysinfo-pending.json') as f:
        output = json.load(f)
    assert output == {'usb': []}


@pytest.mark.asyncio
async def test_collect_no_timestamp(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', [])
    monkeypatch.setattr(time, 'time', lambda: 1000)

    assert helper.data.get('timestamp') is None
    assert not await helper.collect()
    assert helper.data.get('timestamp') == 1000


@pytest.mark.asyncio
async def test_collect_invalid_timestamp(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', [])
    monkeypatch.setattr(time, 'time', lambda: 1000)

    helper.data['timestamp'] = 'fake'
    assert not await helper.collect()
    assert helper.data.get('timestamp') == 1000


@pytest.mark.asyncio
async def test_collect_small_interval(monkeypatch, data_directory, helper_directory, mock_config):
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', [])
    monkeypatch.setattr(time, 'time', lambda: 1000)

    helper.data['timestamp'] = 999
    assert not await helper.collect()
    assert helper.data.get('timestamp') == 999
    assert not os.access(f'{data_directory}/1000.json', os.F_OK)


@pytest.mark.asyncio
async def test_collect_large_interval(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', [])
    monkeypatch.setattr(time, 'time', lambda: 1000000)

    helper.data['timestamp'] = 1
    assert await helper.collect()
    assert os.access(f'{helper_directory}/pending/sysinfo/1000000.json', os.F_OK)
    assert helper.data['timestamp'] == 1000000


@pytest.mark.asyncio
async def test_collect_dedup(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', ['usb'])
    monkeypatch.setattr(helper, 'list_usb', awaitable(lambda: [collections.OrderedDict([('vid', '1234'), ('pid', '5678')])]))

    with open(f'{data_directory}/sysinfo-pending.json', 'w') as f:
        json.dump({'usb': [collections.OrderedDict([('pid', '5678'), ('vid', '1234')])], 'monitors': []}, f)

    assert not await helper.collect()

    with open(f'{data_directory}/sysinfo-pending.json') as f:
        cache = json.load(f)

    assert len(cache['usb']) == 1
    assert list(cache['usb'][0].keys()) == ['pid', 'vid']


@pytest.mark.asyncio
async def test_collect_dedup_tuples(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', ['system'])
    monkeypatch.setattr(helper, 'list_system', awaitable(lambda: [('branch', 'rel'), ('release', '20230703')]))

    assert not await helper.collect()

    with open(f'{data_directory}/sysinfo-pending.json') as f:
        cache = json.load(f)

    assert len(cache['system']) == 2
    assert cache['system'] == [['branch', 'rel'], ['release', '20230703']]

    monkeypatch.setattr(helper, 'list_system', awaitable(lambda: [('branch', 'main'), ('release', '20230704')]))

    assert not await helper.collect()

    with open(f'{data_directory}/sysinfo-pending.json') as f:
        cache = json.load(f)

    assert len(cache['system']) == 4
    assert cache['system'] == [['branch', 'rel'], ['release', '20230703'], ['branch', 'main'], ['release', '20230704']]


@pytest.mark.asyncio
async def test_collect_return_dict(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', ['system'])
    monkeypatch.setattr(helper, 'list_system', awaitable(lambda: {'branch': 'rel', 'release': '20230703'}))

    assert not await helper.collect()

    with open(f'{data_directory}/sysinfo-pending.json') as f:
        cache = json.load(f)

    assert len(cache['system']) == 1
    assert cache['system'] == [{'branch': 'rel', 'release': '20230703'}]

    monkeypatch.setattr(helper, 'list_system', awaitable(lambda: {'branch': 'main', 'release': '20230704'}))

    assert not await helper.collect()

    with open(f'{data_directory}/sysinfo-pending.json') as f:
        cache = json.load(f)

    assert len(cache['system']) == 2
    assert cache['system'] == [{'branch': 'rel', 'release': '20230703'}, {'branch': 'main', 'release': '20230704'}]


@pytest.mark.asyncio
async def test_collect_switch_types(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', ['system'])
    monkeypatch.setattr(helper, 'list_system', awaitable(lambda: [('branch', 'rel'), ('release', '20230703')]))

    assert not await helper.collect()

    with open(f'{data_directory}/sysinfo-pending.json') as f:
        cache = json.load(f)

    assert len(cache['system']) == 2
    assert cache['system'] == [['branch', 'rel'], ['release', '20230703']]

    monkeypatch.setattr(helper, 'list_system', awaitable(lambda: {'branch': 'main', 'release': '20230704'}))

    assert not await helper.collect()

    with open(f'{data_directory}/sysinfo-pending.json') as f:
        cache = json.load(f)

    assert len(cache['system']) == 3
    assert cache['system'] == [['branch', 'rel'], ['release', '20230703'], {'branch': 'main', 'release': '20230704'}]


@pytest.mark.asyncio
async def test_collect_vram(fake_async_subprocess):
    fake_async_subprocess(stdout=b'abc\nMemory info (GL_NVX_gpu_memory_info):\nDedicated video memory: 1024 MB\nMemory info (GL_NVX_gpu_memory_info):\nDedicated video memory: 2048 MB\n')
    vram = await helper.get_vram()
    assert vram == '1024 MB'


@pytest.mark.asyncio
async def test_collect_no_vram(fake_async_subprocess):
    fake_async_subprocess(stdout=b'abc\n')
    vram = await helper.get_vram()
    assert vram is None


@pytest.mark.asyncio
async def test_collect_mem_swap(open_shim):
    open_shim('''
MemTotal:       32768000 kB
MemFree:         1674856 kB
MemAvailable:    2072596 kB
SwapTotal:      65536000 kB
SwapFree:       36444924 kB
''')
    mem, swap = await helper.get_ram()
    assert mem == '32768000 kB'
    assert swap == '65536000 kB'


@pytest.mark.asyncio
async def test_collect_mem_no_swap(open_shim):
    open_shim('''
MemTotal:       32768000 kB
MemFree:         1674856 kB
MemAvailable:    2072596 kB
SwapFree:       36444924 kB
''')
    mem, swap = await helper.get_ram()
    assert mem == '32768000 kB'
    assert swap is None


@pytest.mark.asyncio
async def test_collect_no_mem_swap(open_shim):
    open_shim('''
MemFree:         1674856 kB
MemAvailable:    2072596 kB
SwapTotal:      65536000 kB
SwapFree:       36444924 kB
''')
    mem, swap = await helper.get_ram()
    assert mem is None
    assert swap == '65536000 kB'


@pytest.mark.asyncio
async def test_collect_append(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', ['usb', 'monitors'])
    monkeypatch.setattr(helper, 'list_usb', awaitable(lambda: [collections.OrderedDict([('vid', '1234'), ('pid', '5678')])]))
    monkeypatch.setattr(helper, 'list_monitors', awaitable(lambda: []))

    with open(f'{data_directory}/sysinfo-pending.json', 'w') as f:
        json.dump({'usb': [], 'monitors': [{'edid': '00'}]}, f)

    assert not await helper.collect()

    with open(f'{data_directory}/sysinfo-pending.json') as f:
        cache = json.load(f)

    assert len(cache['usb']) == 1
    assert len(cache['monitors']) == 1


@pytest.mark.asyncio
async def test_collect_append2(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', ['usb'])
    monkeypatch.setattr(helper, 'list_usb', awaitable(lambda: [collections.OrderedDict([('vid', '1234'), ('pid', '5678')])]))

    with open(f'{data_directory}/sysinfo-pending.json', 'w') as f:
        json.dump({'usb': [{'vid': '5678', 'pid': '1234'}]}, f)

    assert not await helper.collect()

    with open(f'{data_directory}/sysinfo-pending.json') as f:
        cache = json.load(f)

    assert len(cache['usb']) == 2
    assert {'vid': '1234', 'pid': '5678'} in cache['usb']
    assert {'vid': '5678', 'pid': '1234'} in cache['usb']


@pytest.mark.asyncio
async def test_collect_new_section(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['sysinfo'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', ['usb', 'monitors'])
    monkeypatch.setattr(helper, 'list_usb', awaitable(lambda: [collections.OrderedDict([('vid', '1234'), ('pid', '5678')])]))
    monkeypatch.setattr(helper, 'list_monitors', awaitable(lambda: []))

    with open(f'{data_directory}/sysinfo-pending.json', 'w') as f:
        json.dump({'monitors': []}, f)

    assert not await helper.collect()

    with open(f'{data_directory}/sysinfo-pending.json') as f:
        cache = json.load(f)

    assert 'monitors' in cache
    assert len(cache['monitors']) == 0
    assert len(cache['usb']) == 1
    assert {'vid': '1234', 'pid': '5678'} in cache['usb']


def test_read_file_text(open_shim):
    open_shim('text')
    assert helper.read_file('') == 'text'


def test_read_file_binary(open_shim):
    open_shim(b'bytes')
    assert helper.read_file('', binary=True) == b'bytes'


def test_read_file_none(open_shim):
    open_shim(None)
    assert helper.read_file('') is None


@pytest.mark.asyncio
async def test_dbus_get_json(monkeypatch, dbus_daemon):
    monkeypatch.setattr(helper, 'list_usb', awaitable(lambda: [collections.OrderedDict([('vid', '1234'), ('pid', '5678')])]))

    daemon, bus = await dbus_daemon
    usb = sls.dbus.DBusObject(bus, '/com/valvesoftware/SteamOSLogSubmitter/helpers/Sysinfo/Usb')
    iface = await usb.interface('com.valvesoftware.SteamOSLogSubmitter.Sysinfo')
    blob = json.loads(typing.cast(str, await iface.get_json()))
    assert blob == [{'vid': '1234', 'pid': '5678'}]
    await daemon.shutdown()
