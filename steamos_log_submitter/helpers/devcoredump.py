# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import os
import zipfile
from . import Helper, HelperResult

from steamos_log_submitter.aggregators.sentry import SentryEvent


class DevcoredumpHelper(Helper):
    valid_extensions = frozenset({'.zip'})

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        event = SentryEvent(cls.config['dsn'])
        try:
            with open(fname, 'rb') as f:
                event.add_attachment({
                    'mime-type': 'application/zip',
                    'filename': os.path.basename(fname),
                    'data': f.read()
                })
            with zipfile.ZipFile(fname) as zf:
                with zf.open('metadata.json') as f:
                    metadata_json = f.read()
                    metadata = json.loads(metadata_json.decode())
        except zipfile.BadZipFile as e:
            cls.logger.error(f'Invalid zip file: {e}')
            return HelperResult.PERMANENT_ERROR
        except json.decoder.JSONDecodeError as e:
            cls.logger.error('Invalid metadata JSON', exc_info=e)
            return HelperResult.PERMANENT_ERROR
        except OSError as e:
            cls.logger.error(f'Error opening zip file: {e}')
            return HelperResult.TRANSIENT_ERROR

        event.add_attachment({
            'mime-type': 'application/json',
            'filename': 'metadata.json',
            'data': metadata_json
        })

        if 'timestamp' in metadata:
            event.timestamp = metadata['timestamp']
        if 'kernel' in metadata:
            event.tags['kernel'] = metadata['kernel']
        if 'branch' in metadata:
            event.tags['branch'] = metadata['branch']
        if 'failing_device' in metadata:
            event.tags['failing_device'] = metadata['failing_device']
        if 'driver' in metadata:
            event.tags['driver'] = metadata['driver']
            event.fingerprint.append(f'driver:{metadata["driver"]}')

        return HelperResult.PERMANENT_ERROR
