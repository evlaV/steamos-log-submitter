# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import httpx
import json
import pytest
import steamos_log_submitter as sls
import steamos_log_submitter.crash as crash
import steamos_log_submitter.steam as steam
from . import awaitable, fake_request, unreachable


@pytest.mark.asyncio
async def test_bad_start(monkeypatch):
    monkeypatch.setattr(steam, 'get_account_id', lambda: 0)
    monkeypatch.setattr(httpx.AsyncClient, 'post', awaitable(fake_request(400)))
    assert not await crash.upload('holo', version='0', info={})


@pytest.mark.asyncio
async def test_no_file(monkeypatch):
    attempt = 0

    def fake_response(body):
        async def ret(self, url, data=None, *args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                assert url == crash.START_URL
                return httpx.Response(200, content=body.encode())
            if attempt == 2:
                assert url == crash.FINISH_URL
                assert data and data.get('gid') == 111
                return httpx.Response(204)
            assert False
        return ret

    response = json.dumps({'response': {
        'headers': {
            'pairs': []
        },
        'url': 'file:///',
        'gid': 111
    }})
    monkeypatch.setattr(steam, 'get_account_id', lambda: 0)
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response(response))
    assert await crash.upload('holo', version='0', info={})
    assert attempt == 2


@pytest.mark.asyncio
async def test_no_account(monkeypatch):
    monkeypatch.setattr(steam, 'get_account_id', lambda: None)
    monkeypatch.setattr(httpx, 'post', unreachable)
    assert not await crash.upload('holo', version='0', info={})


@pytest.mark.asyncio
async def test_bad_end(monkeypatch):
    attempt = 0

    def fake_response(body):
        async def ret(self, url, data=None, *args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                assert url == crash.START_URL
                return httpx.Response(200, content=body.encode())
            if attempt == 2:
                assert url == crash.FINISH_URL
                assert data and data.get('gid') == 111
                return httpx.Response(400)
            assert False
        return ret

    response = json.dumps({'response': {
        'headers': {
            'pairs': []
        },
        'url': 'file:///',
        'gid': 111
    }})
    monkeypatch.setattr(steam, 'get_account_id', lambda: 0)
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response(response))
    assert not await crash.upload('holo', version='0', info={})
    assert attempt == 2


@pytest.mark.asyncio
async def test_file(monkeypatch):
    attempt = 0

    def fake_response(body):
        async def ret(self, url, data=None, content=None, *args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                assert url == crash.START_URL
                return httpx.Response(200, content=body.encode())
            if attempt == 2:
                assert url == json.loads(body)['response']['url']
                assert data is None
                assert content is not None
                assert isinstance(content, bytes)
                return httpx.Response(204)
            if attempt == 3:
                assert url == crash.FINISH_URL
                assert content is None
                assert data and data.get('gid') == 111
                return httpx.Response(204)
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
    monkeypatch.setattr(steam, 'get_account_id', lambda: 0)
    monkeypatch.setattr(httpx.AsyncClient, 'post', respond)
    monkeypatch.setattr(httpx.AsyncClient, 'put', respond)
    assert await crash.upload('holo', version='0', info={}, dump=file)
    assert attempt == 3


@pytest.mark.asyncio
async def test_rate_limit(monkeypatch):
    attempt = 0

    def fake_response(body):
        async def ret(self, url, data=None, *args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                assert url == crash.START_URL
                return httpx.Response(200, content=body.encode())
            assert False
        return ret

    response = json.dumps({'response': {}})
    file = __file__
    respond = fake_response(response)
    monkeypatch.setattr(steam, 'get_account_id', lambda: 0)
    monkeypatch.setattr(httpx.AsyncClient, 'post', respond)
    monkeypatch.setattr(httpx.AsyncClient, 'put', respond)
    try:
        await crash.upload('holo', version='0', info={}, dump=file)
        assert False
    except sls.exceptions.RateLimitingError:
        pass
    assert attempt == 1
