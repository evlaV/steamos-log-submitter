# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import collections
import json
import logging
import re
import time
import os
from typing import Optional
import steamos_log_submitter as sls

config = sls.get_config(__name__)
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


def collect() -> bool:
    devices = {
        'usb': list_usb(),
        'monitors': list_monitors(),
    }
    os.makedirs(f'{sls.base}/data', exist_ok=True)
    known = {}
    try:
        with open(f'{sls.base}/data/peripherals.json') as f:
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

    with open(f'{sls.base}/data/peripherals.json', 'w') as f:
        json.dump(known, f)

    now = time.time()
    timestamp = config.get('timestamp')
    new_file = False
    if timestamp is not None:
        timestamp = float(timestamp)
        if now - timestamp >= config.get('interval', 60 * 60 * 24 * 7):
            # If last submitted over a week ago, submit now
            os.rename(f'{sls.base}/data/peripherals.json', f'{sls.pending}/peripherals/{now:.0f}.json')
            new_file = True

    if not timestamp or new_file:
        config['timestamp'] = now
        sls.config.write_config()

    return new_file


def submit() -> bool:  # pragma: no cover
    return False

# vim:ts=4:sw=4:et
