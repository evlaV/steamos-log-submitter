# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import collections
import dbus
import json
import logging
import os
import re
import subprocess
import time
from typing import Any, Optional
import steamos_log_submitter as sls
from steamos_log_submitter.crash import upload as upload_crash
from steamos_log_submitter.dbus import DBusObject
from . import HelperResult

config = sls.get_config(__name__)
data = sls.get_data(__name__, defaults={'timestamp': None})
logger = logging.getLogger(__name__)


def read_file(path, binary=False) -> Optional[str]:
    try:
        with open(path, 'rb' if binary else 'r') as f:
            data = f.read()
            if binary:
                return data
            return data.strip()
    except FileNotFoundError:
        return None


def list_usb() -> list[dict[str, Any]]:
    usb = '/sys/bus/usb/devices'
    devices = []
    for dev in os.listdir(usb):
        if dev.startswith('usb'):
            # This is a hub/root
            continue
        vid = read_file(f'{usb}/{dev}/idVendor')
        pid = read_file(f'{usb}/{dev}/idProduct')
        if not vid or not pid:
            continue
        info = {
            'vid': vid,
            'pid': pid,
        }
        manufacturer = read_file(f'{usb}/{dev}/manufacturer')
        if manufacturer is not None:
            info['manufacturer'] = manufacturer

        product = read_file(f'{usb}/{dev}/product')
        if product is not None:
            info['product'] = product

        devices.append(info)
    return devices


def list_monitors() -> list[dict[str, Any]]:
    drm = '/sys/class/drm'
    devices = []
    for dev in os.listdir(drm):
        if not re.match(r'card\d+-', dev):
            continue
        edid = read_file(f'{drm}/{dev}/edid', binary=True)
        if not edid:
            continue
        devices.append({'edid': edid.hex()})
    return devices


def list_bluetooth() -> list[dict[str, Any]]:
    bus = 'org.bluez'
    bluez = DBusObject(bus, '/org/bluez')
    adapters = bluez.list_children()
    devices = []
    for adapter in adapters:
        adapter_object = DBusObject(bus, adapter)
        known = adapter_object.list_children()
        for dev in known:
            dev_object = DBusObject(bus, dev)
            dev_dict = {}
            dev_bluez = dev_object.properties('org.bluez.Device1')
            for name, convert in [
                ('Address', str),
                ('Alias', str),
                ('Blocked', bool),
                ('Bonded', bool),
                ('Class', hex),
                ('Connected', bool),
                ('Icon', str),
                ('Modalias', str),
                ('Name', str),
                ('Paired', bool),
                ('Trusted', bool)
            ]:
                try:
                    dev_dict[name.lower()] = convert(dev_bluez[name])
                except KeyError:
                    pass
            dev_dict['adapter'] = adapter.split('/')[-1]
            devices.append(dev_dict)

    return devices


def list_filesystems() -> list[dict[str, Any]]:
    bus = 'org.freedesktop.UDisks2'
    try:
        findmnt = subprocess.run(['findmnt', '-J', '-o', 'uuid,source,target,fstype,size,used', '-b', '--real', '--list'], capture_output=True, errors='replace', check=True)
    except (subprocess.SubprocessError, OSError) as e:
        logger.error('Failed to exec findmnt', exc_info=e)
        return []
    try:
        mntinfo = json.loads(findmnt.stdout)
    except json.decoder.JSONDecodeError as e:
        logger.error('Got invalid JSON from findmnt', exc_info=e)
        return []
    if 'filesystems' not in mntinfo:
        return []
    filesystems = mntinfo['filesystems']
    for fs in filesystems:
        if fs['size'] is None:
            source = fs['source']
            if not source.startswith('/dev/'):
                logger.info(f'Failed to get size of device {source}: unknown device type')
                continue
            node = '/'.join(source.split('/')[2:])
            try:
                block_dev = DBusObject(bus, f'/org/freedesktop/UDisks2/block_devices/{node}')
                dev_props = block_dev.properties('org.freedesktop.UDisks2.Block')
                fs['size'] = int(dev_props['Size'])
            except (KeyError, dbus.exceptions.DBusException) as e:
                logger.info(f'Failed to get size of device {source}', exc_info=e)

    return filesystems


def list_system() -> list[tuple[str, Any]]:
    sysinfo = [
        ('branch', sls.steam.get_steamos_branch()),
        ('release', sls.util.get_build_id()),
    ]
    try:
        sysinfo.append(('devmode', os.access('/usr/share/steamos/devmode-enabled', os.F_OK)))
    except OSError:
        sysinfo.append(('devmode', False))
    return sysinfo


device_types = {
    'usb': list_usb,
    'bluetooth': list_bluetooth,
    'monitors': list_monitors,
    'filesystems': list_filesystems,
    'system': list_system,
}


def collect() -> bool:
    devices = {type: cb() for type, cb in device_types.items()}
    os.makedirs(sls.data.data_root, exist_ok=True)
    known = {}
    try:
        with open(f'{sls.data.data_root}/sysinfo-pending.json') as f:
            known = json.load(f)
    except FileNotFoundError:
        pass
    except json.decoder.JSONDecodeError:
        logger.warning('Parsing error loading cache file')

    for section in devices.keys():
        # Use an ordered dict to easily deduplicate identical entries
        # while making sure to maintain the order they were added in
        devs = collections.OrderedDict()
        if section in known:
            for dev in known[section]:
                devs[json.dumps(dev)] = True
        for dev in devices[section]:
            if type(dev) in (dict, collections.OrderedDict):
                devs[json.dumps(collections.OrderedDict(sorted(dev.items())))] = True
            if type(dev) == tuple:
                devs[json.dumps(dev)] = True
        known[section] = [json.loads(dev) for dev in devs.keys()]

    with open(f'{sls.data.data_root}/sysinfo-pending.json', 'w') as f:
        json.dump(known, f)

    now = time.time()
    timestamp = data['timestamp']
    new_file = False
    if timestamp is not None:
        if now - timestamp >= config.get('interval', 60 * 60 * 24 * 7):
            # If last submitted over a week ago, submit now
            os.rename(f'{sls.data.data_root}/sysinfo-pending.json', f'{sls.pending}/sysinfo/{now:.0f}.json')
            new_file = True

    if not timestamp or new_file:
        data['timestamp'] = now
        try:
            data.write()
        except OSError as e:
            logger.error('Failed writing updated timestamp information', exc_info=e)

    return new_file


def submit(fname: str) -> HelperResult:
    name, ext = os.path.splitext(os.path.basename(fname))
    if ext != '.json':
        return HelperResult(HelperResult.PERMANENT_ERROR)

    info = {
        'crash_time': int(time.time()),
        'stack': '',
        'note': '',
    }
    return HelperResult.check(upload_crash(product='sysinfo', info=info, dump=fname))
