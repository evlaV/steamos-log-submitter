# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus
import gzip
import json
import logging
import os
import subprocess
import time
from typing import Optional
import steamos_log_submitter as sls
from steamos_log_submitter.crash import upload as upload_crash
from steamos_log_submitter.dbus import DBusObject

config = sls.get_config(__name__)
logger = logging.getLogger(__name__)

units = [
    'jupiter-biosupdate.service',
    'jupiter-controller-update.service',
    'jupiter-fan-control.service',
    'steamos-boot.service',
    'steamos-cfs-debugfs-tunings.service',
    'steamos-create-homedir.service',
    'steamos-devkit-service.service',
    'steamos-finish-oobe-migration.service',
    'steamos-glx-backend.service',
    'steamos-install-grub.service',
    'steamos-install-steamcl.service',
    'steamos-log-submitter.service',
    'steamos-log-submitter.timer',
    'steamos-mkvarboot.service',
    'steamos-offload.target',
    'steamos-settings-importer.service',
    'steamos-update-os-plymouth.service',
    'steamos-update-os.service',
    'steamos-update-os.target',
]


def read_journal(unit: str, cursor: Optional[str] = None) -> tuple[list[dict], str]:
    cmd = ['journalctl', '-o', 'json', '-u', unit]
    if cursor is not None:
        cmd.extend(['--after-cursor', cursor])
    try:
        journal = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        return None

    invocations = {}
    cursor = None
    for line in journal.stdout.decode().split('\n'):
        if not line:
            continue
        log = json.loads(line)
        invocation = log.get('INVOCATION_ID')
        if not invocation:
            invocation = log.get('_SYSTEMD_INVOCATION_ID', '')
        logs = invocations.get(invocation, [])
        logs.append(log)
        invocations[invocation] = logs

        cursor = log['__CURSOR']

    pruned_invocations = []
    for logs in invocations.values():
        if 'UNIT_RESULT' in logs[-1]:
            pruned_invocations.extend(logs)

    return pruned_invocations, cursor


def escape(name: str) -> str:
    alphanumeric = b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    alphanumeric = frozenset(b for b in alphanumeric)
    name = name.encode()
    return ''.join([chr(char) if char in alphanumeric else f'_{char:2x}' for char in name])


def collect() -> bool:
    bus = 'org.freedesktop.systemd1'
    updated = False
    for unit in units:
        try:
            dbus_unit = DBusObject(bus, f'/org/freedesktop/systemd1/unit/{escape(unit)}')
            props = dbus_unit.properties('org.freedesktop.systemd1.Unit')
            state = props['ActiveState']
        except dbus.exceptions.DBusException as e:
            logger.warn(f'Exception getting state of unit {unit}', exc_info=e)
            continue
        if state != 'failed':
            continue

        cursor = config.get(f'{escape(unit)}.cursor')
        journal, cursor = read_journal(unit, cursor)

        if not journal:
            logger.error(f'Failed reading journal for unit {unit}')
            continue

        old_journal = []
        try:
            with gzip.open(f'{sls.pending}/systemd/{escape(unit)}.json.gz', 'rt') as f:
                old_journal = json.load(f)
        except FileNotFoundError:
            pass
        except gzip.BadGzipFile as e:
            logger.error(f'Failed to decompress pending/systemd/{escape(unit)}.json.gz', exc_info=e)
        except IOError as e:
            logger.error(f'Failed loading log pending/systemd/{escape(unit)}.json.gz', exc_info=e)
            continue

        old_journal.extend(journal)
        journal = old_journal

        try:
            with gzip.open(f'{sls.pending}/systemd/{escape(unit)}.json.gz', 'wt') as f:
                json.dump(journal, f)
            config[f'{escape(unit)}.cursor'] = cursor
            updated = True
        except IOError as e:
            logger.error(f'Failed writing log pending/systemd/{escape(unit)}.json.gz', exc_info=e)

    if updated:
        sls.config.write_config()

    return updated


def submit(fname: str) -> bool:
    name, ext = os.path.splitext(os.path.basename(fname))
    if ext != '.json.gz':
        return False

    info = {
        'crash_time': int(time.time()),
        'stack': '',
        'note': '',
    }
    return upload_crash(product='systemd', info=info, dump=fname)
