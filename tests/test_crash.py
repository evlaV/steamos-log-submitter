# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import requests
import steamos_log_submitter.crash as crash
import steamos_log_submitter.steam as steam
from . import fake_request


def test_bad_start(monkeypatch):
    monkeypatch.setattr(steam, 'get_steam_account_id', lambda: None)
    monkeypatch.setattr(requests, 'post', fake_request(400))
    assert not crash.upload('holo', version=0, info={})


def test_no_file(monkeypatch):
    attempt = 0

    def fake_response(body):
        def ret(url, data=None, *args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                assert url == crash.start_url
                r = requests.Response()
                r.status_code = 200
                r._content = body.encode()
                return r
            if attempt == 2:
                assert url == crash.finish_url
                assert data and data.get('gid') == 111
                r = requests.Response()
                r.status_code = 204
                return r
            assert False
        return ret

    response = json.dumps({'response': {
        'headers': {
            'pairs': []
        },
        'url': 'file:///',
        'gid': 111
    }})
    monkeypatch.setattr(steam, 'get_steam_account_id', lambda: None)
    monkeypatch.setattr(requests, 'post', fake_response(response))
    assert crash.upload('holo', version=0, info={})
    assert attempt == 2


def test_bad_end(monkeypatch):
    attempt = 0

    def fake_response(body):
        def ret(url, data=None, *args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                assert url == crash.start_url
                r = requests.Response()
                r.status_code = 200
                r._content = body.encode()
                return r
            if attempt == 2:
                assert url == crash.finish_url
                assert data and data.get('gid') == 111
                r = requests.Response()
                r.status_code = 400
                return r
            assert False
        return ret

    response = json.dumps({'response': {
        'headers': {
            'pairs': []
        },
        'url': 'file:///',
        'gid': 111
    }})
    monkeypatch.setattr(steam, 'get_steam_account_id', lambda: None)
    monkeypatch.setattr(requests, 'post', fake_response(response))
    assert not crash.upload('holo', version=0, info={})
    assert attempt == 2


def test_file(monkeypatch):
    attempt = 0

    def fake_response(body):
        def ret(url, data=None, *args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                assert url == crash.start_url
                r = requests.Response()
                r.status_code = 200
                r._content = body.encode()
                return r
            if attempt == 2:
                assert url == json.loads(body)['response']['url']
                assert data is not None
                assert data.read
                r = requests.Response()
                r.status_code = 204
                return r
            if attempt == 3:
                assert url == crash.finish_url
                assert data and data.get('gid') == 111
                r = requests.Response()
                r.status_code = 204
                return r
            assert False
        return ret

    response = json.dumps({'response': {
        'headers': {
            'pairs': []
        },
        'url': 'file:///',
        'gid': 111
    }})
    file = __file__
    respond = fake_response(response)
    monkeypatch.setattr(steam, 'get_steam_account_id', lambda: None)
    monkeypatch.setattr(requests, 'post', respond)
    monkeypatch.setattr(requests, 'put', respond)
    assert crash.upload('holo', version=0, info={}, dump=file)
    assert attempt == 3
