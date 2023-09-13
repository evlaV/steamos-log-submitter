# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import httpx
import logging
import os
from typing import Final, Optional

import steamos_log_submitter as sls
from steamos_log_submitter.types import JSONEncodable

__all__ = [
    'upload',
]

START_URL: Final[str] = "https://api.steampowered.com/ICrashReportService/StartCrashUpload/v1"
FINISH_URL: Final[str] = "https://api.steampowered.com/ICrashReportService/FinishCrashUpload/v1"

logger = logging.getLogger(__name__)


async def upload(product: str, *,
                 info: dict[str, JSONEncodable],
                 build: Optional[str] = None,
                 version: Optional[str] = None,
                 dump: Optional[str] = None) -> bool:
    logger.info(f'Uploading crash log for {product} (build: {build}, version: {version})')
    account = sls.steam.get_steam_account_id()
    if account is None:
        logger.warning('No Steam account configured, rejecting crash upload')
        return False

    info = dict(info)
    info.update({
        'steamid': account,
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

    async with httpx.AsyncClient() as client:
        start = await client.post(START_URL, data=info)
        if start.status_code // 100 != 2:
            logger.warning(f'Crash log StartCrashUpload returned {start.status_code}')
            return False
        logger.debug(f'Crash log StartCrashUpload returned {start.status_code}')

        response = start.json()['response']
        if not response:
            logger.warning('Got empty response from StartCrashUpload -- are we being rate-limited?')
            raise sls.exceptions.RateLimitingError()

        if dump:
            headers = {pair['name']: pair['value'] for pair in response['headers']['pairs']}
            with open(dump, 'rb') as f:
                put = await client.put(response['url'], headers=headers, content=f.read())
            if put.status_code // 100 != 2:
                logger.warning(f'Crash log bucket PUT returned {put.status_code}')
                return False
            logger.debug(f'Crash log bucket PUT returned {put.status_code}')

        finish = await client.post(FINISH_URL, data={'gid': response['gid']})
        if finish.status_code // 100 != 2:
            logger.warning(f'Crash log FinishCrashUpload returned {finish.status_code}')
            return False
        logger.debug(f'Crash log FinishCrashUpload returned {finish.status_code}')

    return True
