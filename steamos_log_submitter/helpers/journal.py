# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2025 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import os
from typing import Optional

import steamos_log_submitter as sls
from steamos_log_submitter.aggregators.sentry import SentryEvent
from steamos_log_submitter.types import JSONEncodable

from . import Helper, HelperResult


class JournalHelper(Helper):
    valid_extensions = frozenset({'.json'})
    system_units = {
        'gpu-trace.service',
        'holo-boot.service',
        'holo-cfs-debugfs-tunings.service',
        'holo-create-homedir.service',
        'holo-dump-info.service',
        'holo-install-grub.service',
        'holo-install-steamcl.service',
        'holo-offload.target',
        'jupiter-biosupdate.service',
        'jupiter-controller-update.service',
        'jupiter-fan-control.service',
        'rauc.service',
        'steam-web-debug-portforward.service',
        'steamos-boot.service',
        'steamos-cfs-debugfs-tunings.service',
        'steamos-create-homedir.service',
        'steamos-devkit-service.service',
        'steamos-dump-info.service',
        'steamos-finish-oobe-migration.service',
        'steamos-install-grub.service',
        'steamos-install-steamcl.service',
        'steamos-kdumpst-layer.service',
        'steamos-log-submitter.service',
        'steamos-manager.service',
        'steamos-mkvarboot.service',
        'steamos-offload.target',
        'steamos-post-update.service',
        'steamos-settings-importer.service',
        'vpower.service',
    }

    user_units = {
        'gamescope-mangoapp.service',
        'gamescope-session.service',
        'gamescope-xbindkeys.service',
        'steam-launcher.service',
        'steam-notif-daemon.service',
        'steamos-manager.service',
        'steamos-powerbuttond.service',
    }

    @classmethod
    async def read_journal(cls, unit: str, invocations: set[str], user: bool = False, cursor: Optional[str] = None) -> tuple[dict[str, list[dict[str, JSONEncodable]]], Optional[str]]:
        logs, cursor = await sls.util.read_journal(unit, cursor, allow_user=user, allow_system=not user)
        if not logs:
            return {}, cursor

        invocation_results: dict[str, list[dict[str, JSONEncodable]]] = {}
        for log in logs:
            if user:
                invocation = log.get('USER_INVOCATION_ID')
            else:
                invocation = log.get('INVOCATION_ID')
            if not invocation:
                invocation = log.get('_SYSTEMD_INVOCATION_ID', '')
            assert isinstance(invocation, str)
            if invocation not in invocations:
                continue
            if '_HOSTNAME' in log:
                del log['_HOSTNAME']
            if '_MACHINE_ID' in log:
                del log['_MACHINE_ID']
            invocation_logs = invocation_results.get(invocation, [])
            invocation_logs.append(log)
            invocation_results[invocation] = invocation_logs

        return invocation_results, cursor

    @classmethod
    async def failed_units(cls, user: bool, cursor: Optional[str] = None) -> tuple[dict[str, set[str]], Optional[str]]:
        if user:
            unit = "user@1000.service"
        else:
            unit = "init.scope"
        if cursor is not None:
            logs, cursor = await sls.util.read_journal(unit, cursor)
        else:
            # Limit first run to only 30 days so it doesn't run forever
            logs, cursor = await sls.util.read_journal(unit, start_ago_ms=2592000000)
        failed: dict[str, set[str]] = {}
        if logs:
            for log in logs:
                if log.get('UNIT_RESULT') not in ('resources', 'protocol', 'timeout', 'exit-code', 'signal', 'core-dump', 'watchdog') and log.get('JOB_RESULT') != 'failed':
                    continue
                if user:
                    invocation = log.get('USER_INVOCATION_ID')
                    failed_unit = log.get('USER_UNIT')
                else:
                    invocation = log.get('INVOCATION_ID')
                    failed_unit = log.get('UNIT')
                if not invocation:
                    invocation = log.get('_SYSTEMD_INVOCATION_ID')
                if invocation is not None and failed_unit is not None:
                    assert isinstance(failed_unit, str)
                    assert isinstance(invocation, str)
                    this_unit = failed.get(failed_unit, set())
                    this_unit.add(invocation)
                    failed[failed_unit] = this_unit
        return failed, cursor

    @classmethod
    def escape(cls, name: str) -> str:
        alphabet = b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        alphanumeric = frozenset(b for b in alphabet)
        bname = name.encode()
        return ''.join([chr(char) if char in alphanumeric else f'_{char:2x}' for char in bname])

    @classmethod
    def unescape(cls, escaped: str) -> str:
        unescaped = []
        progress: Optional[list[str]] = None
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
                        cls.logger.warning(f'Malformed escaped unit name {escaped}')
                    progress = None
        return ''.join(unescaped)

    @classmethod
    async def collect_inner(cls, user: bool) -> None:
        if user:
            cursor_name = 'user_cursor'
            units = cls.user_units
        else:
            cursor_name = 'system_cursor'
            units = cls.system_units

        cursor = cls.data.get(cursor_name)
        assert cursor is None or isinstance(cursor, str)
        failed_units, cursor = await cls.failed_units(user, cursor)
        cls.data[cursor_name] = cursor

        for unit in units:
            if unit not in failed_units:
                continue

            if user:
                unit_name = f'user.{cls.escape(unit)}'
            else:
                unit_name = cls.escape(unit)

            cursor = cls.data.get(f'{unit_name}.cursor')
            assert cursor is None or isinstance(cursor, str)
            journal, cursor = await cls.read_journal(unit, failed_units[unit], user, cursor)

            if not journal:
                cls.logger.error(f'Failed reading journal for unit {unit}')
                continue

            for invocation, new_logs in journal.items():
                old_journal = []
                try:
                    with open(f'{sls.pending}/journal/{unit_name} {invocation}.json', 'rt') as f:
                        old_journal = json.load(f)
                except FileNotFoundError:
                    pass
                except json.decoder.JSONDecodeError as e:
                    cls.logger.warning(f'Failed decoding log pending/journal/{unit_name} {invocation}.json', exc_info=e)
                except OSError as e:
                    cls.logger.error(f'Failed loading log pending/journal/{unit_name} {invocation}.json: {e}')
                    continue

                old_journal.extend(new_logs)
                if not old_journal:
                    continue

                try:
                    with open(f'{sls.pending}/journal/{unit_name} {invocation}.json', 'wt') as f:
                        json.dump(old_journal, f)
                except OSError as e:
                    cls.logger.error(f'Failed writing log pending/journal/{unit_name} {invocation}.json: {e}')
            cls.data[f'{unit_name}.cursor'] = cursor

    @classmethod
    async def collect(cls) -> list[str]:
        await cls.collect_inner(False)
        await cls.collect_inner(True)

        try:
            cls.data.write()
        except OSError as e:
            cls.logger.error(f'Failed writing updated cursor information: {e}')

        return await super().collect()

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        name, _ = os.path.splitext(os.path.basename(fname))

        try:
            with open(fname, 'rb') as f:
                attachment = f.read()
        except OSError:
            return HelperResult.TRANSIENT_ERROR

        tags: dict[str, JSONEncodable] = {}
        extra: dict[str, JSONEncodable] = {}
        fingerprint = []

        name = name.rsplit(' ', 1)[0]
        unit = cls.unescape(name)
        tags['unit'] = unit
        fingerprint.append(f'unit:{unit}')

        extra['kernel'] = os.uname().release

        log = []
        message = [unit]

        try:
            log = json.loads(attachment)
        except (OSError, json.decoder.JSONDecodeError) as e:
            cls.logger.warning('Failed to parse saved journal JSON', exc_info=e)

        for entry in log:
            line = entry.get('MESSAGE')
            if line is None:
                continue
            if isinstance(line, list):
                line = bytes(line).decode(errors="replace")
            message.append(line)

        event = SentryEvent(cls.config['dsn'])
        event.add_attachment({
            'mime-type': 'application/json',
            'filename': os.path.basename(fname),
            'data': attachment
        })
        event.tags = tags
        event.fingerprint = fingerprint
        event.message = '\n'.join(message)
        return HelperResult.check(await event.send())
