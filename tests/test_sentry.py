# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import gzip
import httpx
import pytest
import json
import steamos_log_submitter.sentry as sentry


@pytest.mark.asyncio
async def test_bad_start(monkeypatch):
    attempt = 0

    async def fake_response(url, *args, **kwargs):
        nonlocal attempt
        assert attempt == 0
        attempt += 1
        return httpx.Response(400)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert not await sentry.send_event('', attachments=[{'data': b''}])


@pytest.mark.asyncio
async def test_dsn_parsing(monkeypatch):
    async def fake_response(self, url, headers, *args, **kwargs):
        assert url == 'https://fake@dsn/api/0/store/'
        assert headers.get('X-Sentry-Auth') == 'Sentry sentry_version=7, sentry_key=fake'
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert await sentry.send_event('https://fake@dsn/0')


@pytest.mark.asyncio
async def test_tags(monkeypatch):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('tags') == {'alma-mater': 'MIT'}
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert await sentry.send_event('https://fake@dsn/0', tags={'alma-mater': 'MIT'})


@pytest.mark.asyncio
async def test_fingerprint(monkeypatch):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('fingerprint') == ['gordon', 'freeman']
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert await sentry.send_event('https://fake@dsn/0', fingerprint=['gordon', 'freeman'])


@pytest.mark.asyncio
async def test_message(monkeypatch):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('message') == 'Rise and shine, Mr. Freeman'
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert await sentry.send_event('https://fake@dsn/0', message='Rise and shine, Mr. Freeman')


@pytest.mark.asyncio
async def test_appid(monkeypatch):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('fingerprint') == ['appid:1234']
        assert json.get('tags') == {'appid': '1234'}
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert await sentry.send_event('https://fake@dsn/0', appid=1234)


@pytest.mark.asyncio
async def test_appid_fingerprint_dupe(monkeypatch):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('fingerprint') == ['appid:1234']
        assert json.get('tags') == {'appid': '1234'}
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert await sentry.send_event('https://fake@dsn/0', appid=1234, fingerprint=['appid:1234'])


@pytest.mark.asyncio
async def test_appid_tag_dupe(monkeypatch):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('fingerprint') == ['appid:1234']
        assert json.get('tags') == {'appid': '1234'}
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert await sentry.send_event('https://fake@dsn/0', appid=1234, tags={'appid': '4321'})


@pytest.mark.asyncio
async def test_envelope(monkeypatch):
    event_id = None

    async def fake_response(self, url, **kwargs):
        nonlocal event_id
        if url == 'https://fake@dsn/api/0/store/':
            event_id = kwargs['json']['event_id']
        elif url == 'https://fake@dsn/api/0/envelope/':
            data = gzip.decompress(kwargs['content'])
            line, data = data.split(b'\n', 1)
            header = json.loads(line)
            assert header.get('dsn') == 'https://fake@dsn/0'
            assert header.get('event_id') == event_id
            line, data = data.split(b'\n', 1)
            header = json.loads(line)
            assert header.get('type') == 'attachment'
            assert header.get('filename') == 'enemy.txt'
            assert header.get('content_type') == 'text/plain'
            attachment = data[:header['length']]
            assert attachment == b'headcrab zombie'
            assert data[len(attachment):] == b'\n'
        else:
            assert False
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert await sentry.send_event('https://fake@dsn/0', attachments=[{
        'data': b'headcrab zombie',
        'filename': 'enemy.txt',
        'mime-type': 'text/plain',
    }])


@pytest.mark.asyncio
async def test_envelope_multiple_attachments(monkeypatch):
    event_id = None

    async def fake_response(self, url, **kwargs):
        nonlocal event_id
        if url == 'https://fake@dsn/api/0/store/':
            pass
        elif url == 'https://fake@dsn/api/0/envelope/':
            data = gzip.decompress(kwargs['content'])
            line, data = data.split(b'\n', 1)
            attachment_num = 0
            while len(data):
                line, data = data.split(b'\n', 1)
                header = json.loads(line)
                assert header.get('type') == 'attachment'
                attachment = data[:header['length']]
                assert data[header['length']] == ord('\n')
                data = data[header['length'] + 1:]
                assert attachment_num < 2
                if attachment_num == 0:
                    assert attachment == b'crowbar'
                elif attachment_num == 1:
                    assert attachment == b'gravity gun'
                attachment_num += 1
        else:
            assert False
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert await sentry.send_event('https://fake@dsn/0', attachments=[
        {
            'data': b'crowbar',
        },
        {
            'data': b'gravity gun',
        }
    ])


@pytest.mark.asyncio
async def test_envelope_timestamp(monkeypatch):
    async def fake_response(self, url, **kwargs):
        if url == 'https://fake@dsn/api/0/store/':
            assert kwargs['json']['timestamp'] == 0.1
        elif url == 'https://fake@dsn/api/0/envelope/':
            data = gzip.decompress(kwargs['content'])
            line, data = data.split(b'\n', 1)
            header = json.loads(line)
            assert isinstance(header.get('sent_at'), str)
        else:
            assert False
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    assert await sentry.send_event('https://fake@dsn/0', timestamp=0.1, attachments=[{'data': b''}])
