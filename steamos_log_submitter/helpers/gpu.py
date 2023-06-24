# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
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
    if ext != '.log':
        return False

    try:
        with open(fname, 'rb') as f:
            attachment = f.read()
    except OSError:
        return False

    timestamp = None
    appid = None
    for line in attachment.split(b'\n'):
        try:
            if line.startswith(b'TIMESTAMP='):
                timestamp = float(line.split(b'=')[1]) / 1_000_000_000
            elif line.startswith(b'APPID='):
                appid = int(line.split(b'=')[1])
        except ValueError:
            continue

    attachments = [{
        'mime-type': 'text/plain',
        'filename': 'udev.log',
        'data': attachment
    }]
    return send_event(config['dsn'], attachments=attachments, appid=appid, timestamp=timestamp)
