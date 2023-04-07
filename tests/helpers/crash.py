# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import requests


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
                r = requests.Response()
                r.status_code = 200
                body = json.dumps({'response': response})
                r._content = body.encode()
                return r
            if self.attempt == 2:
                assert url == response['url']
                assert data is not None
                assert data.read
                r = requests.Response()
                r.status_code = 204
                return r
            if self.attempt == 3:
                assert data and data.get('gid') == response['gid']
                r = requests.Response()
                r.status_code = 204
                return r
            assert False
        monkeypatch.setattr(requests, 'post', ret)
        monkeypatch.setattr(requests, 'put', ret)
