# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import collections
import json
import logging
import os
import re
import subprocess
import time
from typing import Optional
import steamos_log_submitter as sls
from steamos_log_submitter.crash import upload as upload_crash
from steamos_log_submitter.dbus import DBusObject

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


def list_usb() -> list[dict]:
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


def list_monitors() -> list[dict]:
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


def list_bluetooth() -> list[dict]:
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


def list_filesystems() -> list[dict]:
    try:
        findmnt = subprocess.run(['findmnt', '-J', '-o', 'uuid,source,target,fstype,size', '-b', '--real', '--list'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    except (subprocess.SubprocessError, OSError) as e:
        logger.error('Failed to exec findmnt', exc_info=e)
        return None
    try:
        mntinfo = json.loads(findmnt.stdout.decode())
    except json.decoder.JSONDecodeError as e:
        logger.error('Got invalid JSON from findmnt', exc_info=e)
        return None
    if 'filesystems' not in mntinfo:
        return None
    return mntinfo['filesystems']


device_types = {
    'usb': list_usb,
    'bluetooth': list_bluetooth,
    'monitors': list_monitors,
    'filesystems': list_filesystems,
}


def collect() -> bool:
    devices = {type: cb() for type, cb in device_types.items()}
    os.makedirs(sls.data.data_root, exist_ok=True)
    known = {}
    try:
        with open(f'{sls.data.data_root}/peripherals.json') as f:
            known = json.load(f)
    except FileNotFoundError:
        pass
    except json.decoder.JSONDecodeError:
        logger.warning('Parsing error loading cache file')

    for section in devices.keys():
        # Use a set to easily deduplicate identical dicts
        devs = set(json.dumps(collections.OrderedDict(sorted(dev.items()))) for dev in devices[section])
        if section in known:
            for dev in known[section]:
                devs.add(json.dumps(dev))
        known[section] = [json.loads(dev) for dev in devs]

    with open(f'{sls.data.data_root}/peripherals.json', 'w') as f:
        json.dump(known, f)

    now = time.time()
    timestamp = data['timestamp']
    new_file = False
    if timestamp is not None:
        if now - timestamp >= config.get('interval', 60 * 60 * 24 * 7):
            # If last submitted over a week ago, submit now
            os.rename(f'{sls.data.data_root}/peripherals.json', f'{sls.pending}/peripherals/{now:.0f}.json')
            new_file = True

    if not timestamp or new_file:
        data['timestamp'] = now
        try:
            data.write()
        except OSError as e:
            logger.error('Failed writing updated timestamp information', exc_info=e)

    return new_file


def submit(fname: str) -> bool:
    name, ext = os.path.splitext(os.path.basename(fname))
    if ext != '.json':
        return False

    info = {
        'crash_time': int(time.time()),
        'stack': '',
        'note': '',
    }
    return upload_crash(product='peripherals', info=info, dump=fname)
