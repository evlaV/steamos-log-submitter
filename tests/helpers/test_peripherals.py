# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import collections
import json
import os
import time
import steamos_log_submitter as sls
import steamos_log_submitter.helpers.peripherals as helper
from .. import data_directory, helper_directory, mock_config, open_shim, patch_module, setup_categories, unreachable  # NOQA: F401
from ..dbus import mock_dbus, MockDBusObject  # NOQA: F401


def make_usb_devs(monkeypatch, devs):
    def read_file(fname):
        dev, node = fname.split('/')[-2:]
        if dev not in devs:
            return None
        return devs[dev].get(node)
    monkeypatch.setattr(helper, 'read_file', read_file)


def test_collect_usb_none(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: [])
    monkeypatch.setattr(helper, 'read_file', unreachable)
    devices = helper.list_usb()
    assert type(devices) == list
    assert not len(devices)


def test_collect_usb_nondev(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['usb1'])
    monkeypatch.setattr(helper, 'read_file', unreachable)
    devices = helper.list_usb()
    assert type(devices) == list
    assert not len(devices)


def test_collect_usb_bad_dev(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['1-1'])
    make_usb_devs(monkeypatch, {'1-1': {}})
    devices = helper.list_usb()
    assert type(devices) == list
    assert not len(devices)


def test_collect_usb_vid_pid_only(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['1-1'])
    make_usb_devs(monkeypatch, {'1-1': {
        'idVendor': '1234',
        'idProduct': '5678'
    }})
    devices = helper.list_usb()
    assert type(devices) == list
    assert len(devices) == 1
    assert devices[0] == {
        'vid': '1234',
        'pid': '5678'
    }


def test_collect_usb_manufacturer(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['1-1'])
    make_usb_devs(monkeypatch, {'1-1': {
        'idVendor': '1234',
        'idProduct': '5678',
        'manufacturer': 'Black Mesa'
    }})
    devices = helper.list_usb()
    assert type(devices) == list
    assert len(devices) == 1
    assert devices[0] == {
        'vid': '1234',
        'pid': '5678',
        'manufacturer': 'Black Mesa'
    }


def test_collect_usb_product(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['1-1'])
    make_usb_devs(monkeypatch, {'1-1': {
        'idVendor': '1234',
        'idProduct': '5678',
        'product': 'Hazardous Environment Suit'
    }})
    devices = helper.list_usb()
    assert type(devices) == list
    assert len(devices) == 1
    assert devices[0] == {
        'vid': '1234',
        'pid': '5678',
        'product': 'Hazardous Environment Suit'
    }


def test_collect_usb_all(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['1-1'])
    make_usb_devs(monkeypatch, {'1-1': {
        'idVendor': '1234',
        'idProduct': '5678',
        'manufacturer': 'Black Mesa',
        'product': 'Hazardous Environment Suit'
    }})
    devices = helper.list_usb()
    assert type(devices) == list
    assert len(devices) == 1
    assert devices[0] == {
        'vid': '1234',
        'pid': '5678',
        'manufacturer': 'Black Mesa',
        'product': 'Hazardous Environment Suit'
    }


def test_collect_bluetooth_no_adapters(monkeypatch, mock_dbus):
    bus = 'org.bluez'
    mock_dbus.add_bus(bus)
    MockDBusObject(bus, '/org/bluez', mock_dbus)

    devices = helper.list_bluetooth()
    assert type(devices) == list
    assert not len(devices)


def test_collect_bluetooth_empty_adapter(monkeypatch, mock_dbus):
    bus = 'org.bluez'
    mock_dbus.add_bus(bus)
    MockDBusObject(bus, '/org/bluez', mock_dbus)
    MockDBusObject(bus, '/org/bluez/hci0', mock_dbus)

    devices = helper.list_bluetooth()
    assert type(devices) == list
    assert not len(devices)


def test_collect_bluetooth_adapter_partial_device(monkeypatch, mock_dbus):
    bus = 'org.bluez'
    mock_dbus.add_bus(bus)
    MockDBusObject(bus, '/org/bluez', mock_dbus)
    MockDBusObject(bus, '/org/bluez/hci0', mock_dbus)
    dev = MockDBusObject(bus, '/org/bluez/hci0/dev_01_02_03_04_05', mock_dbus)
    dev.properties['org.bluez.Device1'] = {
        'Address': '01:02:03:04:05',
        'Name': 'Crowbar'
    }

    devices = helper.list_bluetooth()
    assert type(devices) == list
    assert len(devices) == 1
    assert devices[0] == {'address': '01:02:03:04:05', 'name': 'Crowbar', 'adapter': 'hci0'}


def test_collect_monitors_none(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: [])
    monkeypatch.setattr(helper, 'read_file', unreachable)
    devices = helper.list_monitors()
    assert type(devices) == list
    assert not len(devices)


def test_collect_monitors_other_only(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['version'])
    monkeypatch.setattr(helper, 'read_file', unreachable)
    devices = helper.list_monitors()
    assert type(devices) == list
    assert not len(devices)


def test_collect_monitors_card_only(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['card0'])
    monkeypatch.setattr(helper, 'read_file', unreachable)
    devices = helper.list_monitors()
    assert type(devices) == list
    assert not len(devices)


def test_collect_monitors_no_edid(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', lambda _, binary: None)
    devices = helper.list_monitors()
    assert type(devices) == list
    assert not len(devices)


def test_collect_monitors_edid(monkeypatch):
    def read_file(fname, binary):
        assert binary
        assert fname.endswith('card0-DP-1/edid')
        return b'AAAA'

    monkeypatch.setattr(os, 'listdir', lambda _: ['card0-DP-1'])
    monkeypatch.setattr(helper, 'read_file', read_file)
    devices = helper.list_monitors()
    assert type(devices) == list
    assert len(devices) == 1
    assert devices[0]['edid'] == '41414141'


def test_collect(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['peripherals'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', {
        'usb': lambda: [],
    })

    assert not helper.collect()
    with open(f'{data_directory}/peripherals.json') as f:
        output = json.load(f)
    assert output == {'usb': []}


def test_collect_malformed(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['peripherals'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', {
        'usb': lambda: [],
    })

    with open(f'{data_directory}/peripherals.json', 'w') as f:
        f.write('not json')

    assert not helper.collect()
    with open(f'{data_directory}/peripherals.json') as f:
        output = json.load(f)
    assert output == {'usb': []}


def test_collect_no_timestamp(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['peripherals'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', {})
    monkeypatch.setattr(time, 'time', lambda: 1000)

    assert helper.data.get('timestamp') is None
    assert not helper.collect()
    assert helper.data.get('timestamp') == 1000


def test_collect_small_interval(monkeypatch, data_directory, helper_directory, mock_config):
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', {})
    monkeypatch.setattr(time, 'time', lambda: 1000)

    helper.data['timestamp'] = 999
    assert not helper.collect()
    assert helper.data.get('timestamp') == 999
    assert not os.access(f'{data_directory}/1000.json', os.F_OK)


def test_collect_large_interval(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['peripherals'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', {})
    monkeypatch.setattr(time, 'time', lambda: 1000000)

    helper.data['timestamp'] = 1
    assert helper.collect()
    assert os.access(f'{helper_directory}/pending/peripherals/1000000.json', os.F_OK)
    assert helper.data['timestamp'] == 1000000


def test_collect_dedup(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['peripherals'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', {
        'usb': lambda: [collections.OrderedDict([('vid', '1234'), ('pid', '5678')])],
    })

    with open(f'{data_directory}/peripherals.json', 'w') as f:
        json.dump({'usb': [collections.OrderedDict([('pid', '5678'), ('vid', '1234')])], 'monitors': []}, f)

    assert not helper.collect()

    with open(f'{data_directory}/peripherals.json') as f:
        cache = json.load(f)

    assert len(cache['usb']) == 1
    assert list(cache['usb'][0].keys()) == ['pid', 'vid']


def test_collect_append(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['peripherals'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', {
        'usb': lambda: [collections.OrderedDict([('vid', '1234'), ('pid', '5678')])],
        'monitors': lambda: [],
    })

    with open(f'{data_directory}/peripherals.json', 'w') as f:
        json.dump({'usb': [], 'monitors': [{'edid': '00'}]}, f)

    assert not helper.collect()

    with open(f'{data_directory}/peripherals.json') as f:
        cache = json.load(f)

    assert len(cache['usb']) == 1
    assert len(cache['monitors']) == 1


def test_collect_append2(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['peripherals'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', {
        'usb': lambda: [collections.OrderedDict([('vid', '1234'), ('pid', '5678')])],
    })

    with open(f'{data_directory}/peripherals.json', 'w') as f:
        json.dump({'usb': [{'vid': '5678', 'pid': '1234'}]}, f)

    assert not helper.collect()

    with open(f'{data_directory}/peripherals.json') as f:
        cache = json.load(f)

    assert len(cache['usb']) == 2
    assert {'vid': '1234', 'pid': '5678'} in cache['usb']
    assert {'vid': '5678', 'pid': '1234'} in cache['usb']


def test_collect_new_section(monkeypatch, data_directory, helper_directory, mock_config):
    setup_categories(['peripherals'])
    monkeypatch.setattr(sls, 'base', helper_directory)
    monkeypatch.setattr(helper, 'device_types', {
        'usb': lambda: [collections.OrderedDict([('vid', '1234'), ('pid', '5678')])],
        'monitors': lambda: [],
    })

    with open(f'{data_directory}/peripherals.json', 'w') as f:
        json.dump({'monitors': []}, f)

    assert not helper.collect()

    with open(f'{data_directory}/peripherals.json') as f:
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


def test_submit_bad_name():
    assert not helper.submit('not-a-log.bin')
