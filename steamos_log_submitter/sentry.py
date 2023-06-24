# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import datetime
import gzip
import io
import json
import logging
import requests
import urllib.parse
import uuid
from typing import Dict, List, Optional
import steamos_log_submitter as sls

logger = logging.getLogger(__name__)


def send_event(dsn: str, *, appid: Optional[int] = None, attachment: bytes = b'', tags: Dict[str, str] = {}, fingerprint: List[str] = []) -> bool:
    raw_envelope = io.BytesIO()
    envelope = gzip.GzipFile(fileobj=raw_envelope, mode='wb')

    def append_json(j):
        envelope.write(json.dumps(j).encode())
        envelope.write(b'\n')

    def append_item(j, item=b''):
        append_json(j)
        envelope.write(item)
        envelope.write(b'\n')

    event_id = uuid.uuid4().hex
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    event = {
        'event_id': event_id,
        'timestamp': timestamp,
        'platform': 'native',
    }

    build_id = sls.util.get_build_id()
    if build_id:
        event['release'] = build_id

    tags = dict(tags)
    fingerprint = list(fingerprint)
    if appid is not None:
        if f'appid:{appid}' not in fingerprint:
            fingerprint.append(f'appid:{appid}')
        tags['appid'] = str(appid)

    if tags:
        event['tags'] = tags
    if fingerprint:
        event['fingerprint'] = fingerprint

    dsn_parsed = urllib.parse.urlparse(dsn)
    store_endpoint = dsn_parsed._replace(path=f'/api{dsn_parsed.path}/store/').geturl()
    envelope_endpoint = dsn_parsed._replace(path=f'/api{dsn_parsed.path}/envelope/').geturl()
    auth = f'Sentry sentry_version=7, sentry_key={dsn_parsed.username}'

    store_post = requests.post(store_endpoint, json=event, headers={
        'X-Sentry-Auth': auth,
        'User-Agent': 'SteamOS Log Submitter',
    })

    if store_post.status_code != 200:
        logger.error(f'Failed to submit event: {store_post.content}')
        return False

    if attachment:
        append_json({
            'dsn': dsn,
            'event_id': event_id,
            'sent_at': timestamp,
        })
        append_item({
            'type': 'attachment',
            'length': len(attachment)
        }, attachment)

        envelope.close()

        envelope_post = requests.post(envelope_endpoint, data=raw_envelope.getvalue(), headers={
            'Content-Type': 'application/x-sentry-envelope',
            'Content-Encoding': 'gzip',
            'X-Sentry-Auth': auth,
            'User-Agent': 'SteamOS Log Submitter',
        })

        if envelope_post.status_code != 200:
            logger.error(f'Failed to submit attachment: {envelope_post.content}')
            return False

    return True
