# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus
import json
import logging
import os
import subprocess
from typing import Optional
import steamos_log_submitter as sls
from steamos_log_submitter.dbus import DBusObject
from steamos_log_submitter.sentry import send_event
from . import HelperResult

config = sls.get_config(__name__)
data = sls.get_data(__name__)
logger = logging.getLogger(__name__)

units = [
    'gpu-trace.service',
    'jupiter-biosupdate.service',
    'jupiter-controller-update.service',
    'jupiter-fan-control.service',
    'rauc.service',
    'steam-web-debug-portforward.service',
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
    except (subprocess.SubprocessError, OSError) as e:
        logger.error('Failed to exec journalctl', exc_info=e)
        return None, None

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


def unescape(escaped: str) -> str:
    unescaped = []
    progress = None
    for char in escaped:
        if progress is None:
            if char != '_':
                unescaped.append(char)
            else:
                progress = []
        else:
            progress.append(char)
            if len(progress) == 2:
                try:
                    unescaped.append(chr(int(''.join(progress), 16)))
                except ValueError:
                    logger.warning(f'Malformed escaped unit name {escaped}')
                progress = None
    return ''.join(unescaped)


def collect() -> bool:
    bus = 'org.freedesktop.systemd1'
    updated = False
    for unit in units:
        try:
            dbus_unit = DBusObject(bus, f'/org/freedesktop/systemd1/unit/{escape(unit)}')
            props = dbus_unit.properties('org.freedesktop.systemd1.Unit')
            state = props['ActiveState']
        except (dbus.exceptions.DBusException, KeyError) as e:
            logger.warning(f'Exception getting state of unit {unit}', exc_info=e)
            continue
        if state != 'failed':
            continue

        cursor = data.get(f'{escape(unit)}.cursor')
        journal, cursor = read_journal(unit, cursor)

        if not journal:
            logger.error(f'Failed reading journal for unit {unit}')
            continue

        old_journal = []
        try:
            with open(f'{sls.pending}/journal/{escape(unit)}.json', 'rt') as f:
                old_journal = json.load(f)
        except FileNotFoundError:
            pass
        except json.decoder.JSONDecodeError as e:
            logger.warning(f'Failed decoding log pending/journal/{escape(unit)}.json', exc_info=e)
        except OSError as e:
            logger.error(f'Failed loading log pending/journal/{escape(unit)}.json', exc_info=e)
            continue

        old_journal.extend(journal)
        journal = old_journal

        try:
            with open(f'{sls.pending}/journal/{escape(unit)}.json', 'wt') as f:
                json.dump(journal, f)
            data[f'{escape(unit)}.cursor'] = cursor
            updated = True
        except OSError as e:
            logger.error(f'Failed writing log pending/journal/{escape(unit)}.json', exc_info=e)

    if updated:
        try:
            data.write()
        except OSError as e:
            logger.error('Failed writing updated cursor information', exc_info=e)

    return updated


def submit(fname: str) -> HelperResult:
    name, ext = os.path.splitext(os.path.basename(fname))
    if ext != '.json':
        return HelperResult(HelperResult.PERMANENT_ERROR)

    try:
        with open(fname, 'rb') as f:
            attachment = f.read()
    except OSError:
        return HelperResult(HelperResult.TRANSIENT_ERROR)

    tags = {}
    fingerprint = []

    unit = unescape(name)
    tags['unit'] = unit
    fingerprint.append(f'unit:{unit}')

    tags['kernel'] = os.uname().release

    attachments = [{
        'mime-type': 'application/json',
        'filename': os.path.basename(fname),
        'data': attachment
    }]
    ok = send_event(config['dsn'],
                    attachments=attachments,
                    tags=tags,
                    fingerprint=fingerprint,
                    message=unit)
    return HelperResult.check(ok)
