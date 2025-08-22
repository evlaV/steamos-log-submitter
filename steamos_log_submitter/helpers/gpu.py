# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2025 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import os
import zipfile
from steamos_log_submitter.aggregators.sentry import SentryEvent
from . import Helper, HelperResult


class GPUHelper(Helper):
    valid_extensions = frozenset({'.zip'})

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        tags = {}
        fingerprint = []
        event = SentryEvent(cls.config['dsn'])
        try:
            with zipfile.ZipFile(fname) as f:
                with f.open('metadata.json') as zf:
                    metadata = zf.read()
                    event.add_attachment({
                        'mime-type': 'application/json',
                        'filename': 'metadata.json',
                        'data': metadata
                    })
            with open(fname, 'rb') as f:
                attachment = f.read()
        except zipfile.BadZipFile:
            return HelperResult.PERMANENT_ERROR
        except OSError:
            return HelperResult.TRANSIENT_ERROR

        try:
            log = json.loads(metadata.decode())
        except json.decoder.JSONDecodeError as e:
            cls.logger.error("Couldn't decode GPU log", exc_info=e)
            return HelperResult(HelperResult.PERMANENT_ERROR)

        timestamp = None
        if 'timestamp' in log:
            try:
                timestamp = float(log['timestamp'])
            except (ValueError, TypeError):
                pass

        message = None
        appid = None
        if 'appid' in log:
            try:
                appid = int(log['appid'])
                message = f'GPU reset ({appid})'
            except (ValueError, TypeError):
                pass

        executable = log.get('executable')
        if executable:
            tags['executable'] = executable
            fingerprint.append(f'executable:{executable}')
            if not message:
                message = f'GPU reset ({executable})'

        comm = log.get('comm')
        if comm:
            tags['comm'] = comm
            fingerprint.append(f'comm:{comm}')
            if not message:
                message = f'GPU reset ({comm})'

        if not message:
            message = 'GPU reset'

        kernel = log.get('kernel')
        if kernel is not None:
            tags['kernel'] = kernel
            fingerprint.append(f'kernel:{kernel}')

        mesa = log.get('mesa')
        if mesa:
            tags['mesa'] = mesa
            fingerprint.append(f'mesa:{mesa}')

        event.add_attachment({
            'mime-type': 'application/zip',
            'filename': os.path.basename(fname),
            'data': attachment
        })
        event.appid = appid
        event.timestamp = timestamp
        event.tags = tags
        event.fingerprint = fingerprint
        event.message = message
        return HelperResult.check(await event.send())
