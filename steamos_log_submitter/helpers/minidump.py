# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import httpx
import json
import os
import steamos_log_submitter as sls
from . import Helper, HelperResult


class MinidumpHelper(Helper):
    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        name, ext = os.path.splitext(os.path.basename(fname))
        if ext not in ('.md', '.dmp'):
            return HelperResult(HelperResult.PERMANENT_ERROR)
        name_parts = name.split('-')

        metadata = {}
        try:
            appid = int(name_parts[-1])
            metadata['sentry[tags][appid]'] = appid
        except ValueError:
            # Invalid appid
            pass

        build_id = sls.util.get_build_id()
        if build_id is not None:
            metadata['sentry[tags][build_id]'] = build_id

        environment = sls.steam.get_steamos_branch()
        if environment:
            metadata['sentry[environment]'] = environment

        for attr in ('executable', 'comm', 'path'):
            try:
                value = os.getxattr(fname, f'user.{attr}')
                metadata[f'sentry[tags][{attr}]'] = value
            except IOError:
                cls.logger.warning(f'Failed to get {attr} xattr on minidump.')

        cls.logger.debug(f'Uploading minidump with metadata {metadata}')
        async with httpx.AsyncClient() as client:
            post = await client.post(cls.config['dsn'], files={'upload_file_minidump': open(fname, 'rb')}, data=metadata)

        if post.status_code != 200:
            cls.logger.error(f'Attempting to upload minidump {name} failed with status {post.status_code}')
        if post.status_code == 400:
            try:
                data = post.json()
                if data.get('detail') == 'invalid minidump':
                    cls.logger.warning('Minidump appears corrupted. Removing to avoid indefinite retrying.')
                    return HelperResult(HelperResult.PERMANENT_ERROR)
            except json.decoder.JSONDecodeError:
                pass

        return HelperResult.check(post.status_code == 200)
