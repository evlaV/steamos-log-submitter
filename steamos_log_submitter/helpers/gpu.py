# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import os
from . import HelperResult, SentryHelper


class GPUHelper(SentryHelper):
    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
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
        try:
            log = json.loads(attachment.decode())
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

        if not message:
            message = 'GPU reset'

        kernel = log.get('kernel')
        if kernel is not None:
            tags['kernel'] = kernel
            fingerprint.append(f'kernel:{kernel}')

        attachments = [{
            'mime-type': 'application/json',
            'filename': os.path.basename(fname),
            'data': attachment
        }]
        return await cls.send_event(attachments=attachments,
                                    appid=appid,
                                    timestamp=timestamp,
                                    tags=tags,
                                    fingerprint=fingerprint,
                                    message=message)
