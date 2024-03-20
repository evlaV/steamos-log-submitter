# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import gzip
import httpx
import pytest
import json
import steamos_log_submitter as sls
import steamos_log_submitter.sentry as sentry
from . import mock_config, open_shim  # NOQA: F401


@pytest.mark.asyncio
async def test_bad_start(monkeypatch):
    attempt = 0

    async def fake_response(url, *args, **kwargs):
        nonlocal attempt
        assert attempt == 0
        attempt += 1
        return httpx.Response(400)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    event = sentry.SentryEvent('')
    assert not await event.send()


@pytest.mark.asyncio
async def test_dsn_parsing(monkeypatch):
    async def fake_response(self, url, headers, *args, **kwargs):
        assert url == 'https://fake@dsn/api/0/store/'
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    event = sentry.SentryEvent('https://fake@dsn/0')
    assert await event.send()


@pytest.mark.asyncio
async def test_tags(mock_config, monkeypatch, open_shim):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('tags') == {'alma-mater': 'MIT'}
        return httpx.Response(200)

    open_shim.enoent()
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    event = sentry.SentryEvent('https://fake@dsn/0')
    event.tags = {'alma-mater': 'MIT'}
    assert await event.send()


@pytest.mark.asyncio
async def test_id_tags(mock_config, monkeypatch, open_shim):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('tags') == {'unit_id': sls.util.telemetry_unit_id()}
        assert json.get('user') == {'id': sls.util.telemetry_unit_id()}
        return httpx.Response(200)

    open_shim.enoent()
    monkeypatch.setattr(sls.util, 'telemetry_unit_id', lambda: '1234')
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    event = sentry.SentryEvent('https://fake@dsn/0')
    assert await event.send()


@pytest.mark.asyncio
async def test_fingerprint(monkeypatch):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('fingerprint') == ['gordon', 'freeman']
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    event = sentry.SentryEvent('https://fake@dsn/0')
    event.fingerprint = ['gordon', 'freeman']
    assert await event.send()


@pytest.mark.asyncio
async def test_extra(mock_config, monkeypatch, open_shim):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('extra') == {'sls.version': sls.__version__}
        return httpx.Response(200)

    open_shim.enoent()
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    event = sentry.SentryEvent('https://fake@dsn/0')
    assert await event.send()


@pytest.mark.asyncio
async def test_message(monkeypatch):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('message') == 'Rise and shine, Mr. Freeman'
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    event = sentry.SentryEvent('https://fake@dsn/0')
    event.message = 'Rise and shine, Mr. Freeman'
    assert await event.send()


@pytest.mark.asyncio
async def test_appid(mock_config, monkeypatch, open_shim):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('fingerprint') == ['appid:1234']
        assert json.get('tags') == {'appid': 1234}
        return httpx.Response(200)

    open_shim.enoent()
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    event = sentry.SentryEvent('https://fake@dsn/0')
    event.appid = 1234
    assert await event.send()


@pytest.mark.asyncio
async def test_appid_fingerprint_dupe(mock_config, monkeypatch, open_shim):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('fingerprint') == ['appid:1234']
        assert json.get('tags') == {'appid': 1234}
        return httpx.Response(200)

    open_shim.enoent()
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    event = sentry.SentryEvent('https://fake@dsn/0')
    event.appid = 1234
    event.fingerprint = ['appid:1234']
    assert await event.send()


@pytest.mark.asyncio
async def test_appid_tag_dupe(mock_config, monkeypatch, open_shim):
    async def fake_response(self, url, json, **kwargs):
        assert json.get('fingerprint') == ['appid:1234']
        assert json.get('tags') == {'appid': 1234}
        return httpx.Response(200)

    open_shim.enoent()
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_response)
    event = sentry.SentryEvent('https://fake@dsn/0')
    event.appid = 1234
    event.tags = {'appid': '1234'}
    assert await event.send()


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
    event = sentry.SentryEvent('https://fake@dsn/0')
    event.add_attachment({
        'data': b'headcrab zombie',
        'filename': 'enemy.txt',
        'mime-type': 'text/plain',
    })
    assert await event.send()


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
    event = sentry.SentryEvent('https://fake@dsn/0')
    event.add_attachment({'data': b'crowbar'}, {'data': b'gravity gun'})
    assert await event.send()


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
    event = sentry.SentryEvent('https://fake@dsn/0')
    event.timestamp = 0.1
    event.add_attachment({'data': b''})
    assert await event.send()
