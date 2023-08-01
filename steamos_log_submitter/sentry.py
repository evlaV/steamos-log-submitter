# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import datetime
import gzip
import httpx
import io
import json
import logging
import urllib.parse
import uuid
from collections.abc import Iterable
from typing import Any, Optional
import steamos_log_submitter as sls
from steamos_log_submitter.types import JSONEncodable

logger = logging.getLogger(__name__)


async def send_event(dsn: str, *,
                     appid: Optional[int] = None,
                     attachments: Iterable[dict[str, Any]] = (),
                     tags: dict[str, JSONEncodable] = {},
                     fingerprint: Iterable[str] = (),
                     timestamp: Optional[float] = None,
                     environment: Optional[str] = None,
                     message: Optional[str] = None) -> bool:
    raw_envelope = io.BytesIO()
    envelope = gzip.GzipFile(fileobj=raw_envelope, mode='wb')

    def append_json(j: JSONEncodable) -> None:
        envelope.write(json.dumps(j).encode())
        envelope.write(b'\n')

    def append_item(j: JSONEncodable, item: bytes = b'') -> None:
        append_json(j)
        envelope.write(item)
        envelope.write(b'\n')

    event_id = uuid.uuid4().hex
    sent_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    event: dict[str, JSONEncodable] = {
        'event_id': event_id,
        'timestamp': timestamp or sent_at,
        'platform': 'native',
    }

    build_id = sls.util.get_build_id()
    if build_id:
        event['release'] = build_id

    if message:
        event['message'] = message

    if not environment:
        environment = sls.steam.get_steamos_branch()
    if environment:
        event['environment'] = environment

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

    async with httpx.AsyncClient() as client:
        store_post = await client.post(store_endpoint, json=event, headers={
            'X-Sentry-Auth': auth,
            'User-Agent': 'SteamOS Log Submitter',
        })

        if store_post.status_code != 200:
            logger.error(f'Failed to submit event: {store_post.content.decode()}')
            return False

        if attachments:
            append_json({
                'dsn': dsn,
                'event_id': event_id,
                'sent_at': sent_at,
            })

            for attachment in attachments:
                attachment_info: dict[str, JSONEncodable] = {
                    'type': 'attachment',
                    'length': len(attachment['data'])
                }
                if 'mime-type' in attachment:
                    attachment_info['content_type'] = attachment['mime-type']
                if 'filename' in attachment:
                    attachment_info['filename'] = attachment['filename']
                append_item(attachment_info, attachment['data'])

            envelope.close()

            envelope_post = await client.post(envelope_endpoint, content=raw_envelope.getvalue(), headers={
                'Content-Type': 'application/x-sentry-envelope',
                'Content-Encoding': 'gzip',
                'X-Sentry-Auth': auth,
                'User-Agent': 'SteamOS Log Submitter',
            })

            if envelope_post.status_code != 200:
                logger.error(f'Failed to submit attachment: {envelope_post.content.decode()}')
                return False

    return True
