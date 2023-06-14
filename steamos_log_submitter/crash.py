# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import os
import requests
import steamos_log_submitter as sls

start_url = "https://api.steampowered.com/ICrashReportService/StartCrashUpload/v1"
finish_url = "https://api.steampowered.com/ICrashReportService/FinishCrashUpload/v1"

logger = logging.getLogger(__name__)


def upload(product, *, build=None, version=None, info, dump=None) -> bool:
    logger.info(f'Uploading crash log for {product} (build: {build}, version: {version})')
    account = sls.steam.get_steam_account_id()

    info = dict(info)
    info.update({
        'steamid': account or 'null',
        'have_dump_file': 1 if dump else 0,
        'product': product,
        'build': build or sls.util.get_build_id(),
        'version': version or os.uname().release,
        'platform': 'linux',
        'format': 'json'
    })
    if dump:
        info['dump_file_size'] = os.stat(dump).st_size
    logger.debug(f'Crash log info dict:\n{info}')

    start = requests.post(start_url, data=info)
    logger.debug(f'Crash log StartCrashUpload returned {start.status_code}')
    if start.status_code // 100 != 2:
        return False

    response = start.json()['response']

    if dump:
        headers = {pair['name']: pair['value'] for pair in response['headers']['pairs']}
        put = requests.put(response['url'], headers=headers, data=open(dump, 'rb'))
        logger.debug(f'Crash log bucket PUT returned {put.status_code}')
        if put.status_code // 100 != 2:
            return False

    finish = requests.post(finish_url, data={'gid': response['gid']})
    logger.debug(f'Crash log FinishCrashUpload returned {finish.status_code}')
    if finish.status_code // 100 != 2:
        return False

    return True
