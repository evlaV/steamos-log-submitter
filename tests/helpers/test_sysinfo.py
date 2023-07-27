# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import collections
import json
import os
import pytest
import subprocess
import time
import steamos_log_submitter as sls
from steamos_log_submitter.helpers import create_helper, HelperResult
from .. import always_raise, awaitable, open_shim, setup_categories, unreachable
from .. import data_directory, helper_directory, mock_config, patch_module  # NOQA: F401
from ..dbus import mock_dbus, MockDBusObject  # NOQA: F401

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
async def test_collect_monitors_no_edid(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', lambda _, binary: None)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert not len(devices)


@pytest.mark.asyncio
async def test_collect_monitors_edid(monkeypatch):
    def read_file(fname, binary):
        assert binary
        assert fname.endswith('card0-DP-1/edid')
        return b'AAAA'

    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', read_file)
    devices = await helper.list_monitors()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0]['edid'] == '41414141'


@pytest.mark.asyncio
async def test_collect_filesystems_raise(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', always_raise(OSError))
    assert await helper.list_filesystems() == []


@pytest.mark.asyncio
async def test_collect_filesystems_malformed(monkeypatch):
    def fake_subprocess(*args, **kwargs):
        ret = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = '!'
        return ret

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    fs = await helper.list_filesystems()
    assert fs == []


@pytest.mark.asyncio
async def test_collect_filesystems_missing(monkeypatch):
    def fake_subprocess(*args, **kwargs):
        ret = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = '{"wrong_things":"go_here"}'
        return ret

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    fs = await helper.list_filesystems()
    assert fs == []


@pytest.mark.asyncio
async def test_collect_filesystems_get_missing_size(monkeypatch, mock_dbus):
    def fake_subprocess(*args, **kwargs):
        ret = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = json.dumps({'filesystems': [{'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'bitbucket', 'size': None}]})
        return ret

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)
    bus = 'org.freedesktop.UDisks2'
    mock_dbus.add_bus(bus)
    block_dev = MockDBusObject(bus, '/org/freedesktop/UDisks2/block_devices/null', mock_dbus)
    block_dev.properties['org.freedesktop.UDisks2.Block'] = {
        'Size': 0,
    }

    fs = await helper.list_filesystems()
    assert fs == [{'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'bitbucket', 'size': 0}]


@pytest.mark.asyncio
async def test_collect_filesystems_unknown_missing_size(monkeypatch, mock_dbus):
    def fake_subprocess(*args, **kwargs):
        ret = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = json.dumps({'filesystems': [{'uuid': None, 'source': 'resonance', 'target': '/', 'fstype': 'cascade', 'size': None}]})
        return ret

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)
    bus = 'org.freedesktop.UDisks2'
    mock_dbus.add_bus(bus)

    fs = await helper.list_filesystems()
    assert fs == [{'uuid': None, 'source': 'resonance', 'target': '/', 'fstype': 'cascade', 'size': None}]


@pytest.mark.asyncio
async def test_collect_filesystems_clean(monkeypatch):
    def fake_subprocess(*args, **kwargs):
        ret = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = json.dumps({'filesystems': [{'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'bitbucket', 'size': 0}]})
        return ret

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    fs = await helper.list_filesystems()
    assert fs == [{'uuid': None, 'source': '/dev/null', 'target': '/', 'fstype': 'bitbucket', 'size': 0}]


@pytest.mark.asyncio
async def test_collect_system(monkeypatch):
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_build_id', lambda: '20230704')
    monkeypatch.setattr(os, 'access', lambda x, y: True)

    assert dict(await helper.list_system()) == {
        'branch': 'main',
        'release': '20230704',
        'devmode': True,
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


def test_read_file_text(monkeypatch):
    monkeypatch.setattr(builtins, 'open', open_shim('text'))
    assert helper.read_file('') == 'text'


def test_read_file_binary(monkeypatch):
    monkeypatch.setattr(builtins, 'open', open_shim(b'bytes'))
    assert helper.read_file('', binary=True) == b'bytes'


def test_read_file_none(monkeypatch):
    monkeypatch.setattr(builtins, 'open', open_shim(None))
    assert helper.read_file('') is None


@pytest.mark.asyncio
async def test_submit_bad_name():
    assert (await helper.submit('not-a-log.bin')).code == HelperResult.PERMANENT_ERROR
