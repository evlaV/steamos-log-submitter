import os
import steamos_log_submitter.helpers.peripherals as helper
from .. import unreachable


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

# vim:ts=4:sw=4:et
