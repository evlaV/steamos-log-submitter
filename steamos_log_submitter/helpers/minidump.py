# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import os
import requests
import steamos_log_submitter as sls

config = sls.get_config(__name__)
logger = logging.getLogger(__name__)
dsn = config.get('dsn')


def collect() -> bool:  # pragma: no cover
    return False


def submit(fname: str) -> bool:
    name, ext = os.path.splitext(os.path.basename(fname))
    if ext not in ('.md', '.dmp'):
        return False
    name_parts = name.split('-')

    metadata = {}
    try:
        appid = int(name_parts[-1])
        metadata['sentry[tags][appid]'] = appid
    except ValueError:
        # Invalid appid
        pass

    account = sls.util.get_steam_account_id()
    if account is not None:
        metadata['sentry[tags][steam_id]'] = account

    build_id = sls.util.get_build_id()
    if build_id is not None:
        metadata['sentry[tags][build_id]'] = build_id

    post = requests.post(dsn, files={'upload_file_minidump': open(fname, 'rb')}, data=metadata)

    if post.status_code != 200:
        logger.error(f'Attempting to upload minidump {name} failed with status {post.status_code}')
    if post.status_code == 400:
        data = post.json()
        if data.get('detail') == 'invalid minidump':
            logger.warning('Minidump appears corrupted. Removing to avoid indefinite retrying.')
            # Just lie so it gets cleaned up
            return True

    return post.status_code == 200
