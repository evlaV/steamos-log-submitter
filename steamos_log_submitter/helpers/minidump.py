# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import os
import requests
import sys
import steamos_log_submitter as sls

config = sls.get_config(__name__)
dsn = config.get('dsn')

def collect() -> bool:  # pragma: no cover
    return False


def submit(fname : str) -> bool:
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

    return post.status_code == 200

# vim:ts=4:sw=4:et
