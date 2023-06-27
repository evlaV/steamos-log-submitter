# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import logging
import os
import steamos_log_submitter as sls
from steamos_log_submitter.sentry import send_event

config = sls.get_config(__name__)
logger = logging.getLogger(__name__)


def collect() -> bool:
    return False


def submit(fname: str) -> bool:
    name, ext = os.path.splitext(os.path.basename(fname))
    if ext != '.json':
        return False

    try:
        with open(fname, 'rb') as f:
            attachment = f.read()
    except OSError:
        return False

    tags = {}
    fingerprint = []
    try:
        log = json.loads(attachment.decode())
    except json.decoder.JSONDecodeError as e:
        logger.error("Couldn't decode GPU log", exc_info=e)
        return True  # lie

    timestamp = None
    if 'timestamp' in log:
        try:
            timestamp = float(log['timestamp'])
        except (ValueError, TypeError):
            pass

    appid = None
    if 'appid' in log:
        try:
            appid = int(log['appid'])
        except (ValueError, TypeError):
            pass

    executable = log.get('executable')
    if executable:
        tags['executable'] = executable
        fingerprint.append(f'executable:{executable}')

    kernel = log.get('kernel')
    if kernel is not None:
        tags['kernel'] = kernel
        fingerprint.append(f'kernel:{kernel}')

    attachments = [{
        'mime-type': 'application/json',
        'filename': os.path.basename(fname),
        'data': attachment
    }]
    return send_event(config['dsn'],
                      attachments=attachments,
                      appid=appid,
                      timestamp=timestamp,
                      tags=tags,
                      fingerprint=fingerprint)
