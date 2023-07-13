# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import httpx
import json


class FakeResponse:
    def __init__(self):
        self.attempt = 0

    def success(self, monkeypatch):
        response = {
            'headers': {
                'pairs': []
            },
            'url': 'file:///',
            'gid': 111
        }
        self.attempt = 0

        def ret(url, data=None, *args, **kwargs):
            self.attempt += 1
            if self.attempt == 1:
                body = json.dumps({'response': response})
                return httpx.Response(200, content=body.encode())
            if self.attempt == 2:
                assert url == response['url']
                assert data is not None
                assert data.read
                return httpx.Response(204)
            if self.attempt == 3:
                assert data and data.get('gid') == response['gid']
                return httpx.Response(204)
            assert False
        monkeypatch.setattr(httpx, 'post', ret)
        monkeypatch.setattr(httpx, 'put', ret)
