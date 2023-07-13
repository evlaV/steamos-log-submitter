# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import gzip
import httpx
import json
import steamos_log_submitter.sentry as sentry


def test_bad_start(monkeypatch):
    attempt = 0

    def fake_response(url, *args, **kwargs):
        nonlocal attempt
        assert attempt == 0
        attempt += 1
        return httpx.Response(400)

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert not sentry.send_event('', attachments=[{'data': b''}])


def test_dsn_parsing(monkeypatch):
    def fake_response(url, headers, *args, **kwargs):
        assert url == 'https://fake@dsn/api/0/store/'
        assert headers.get('X-Sentry-Auth') == 'Sentry sentry_version=7, sentry_key=fake'
        return httpx.Response(200)

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert sentry.send_event('https://fake@dsn/0')


def test_tags(monkeypatch):
    def fake_response(url, json, **kwargs):
        assert json.get('tags') == {'alma-mater': 'MIT'}
        return httpx.Response(200)

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert sentry.send_event('https://fake@dsn/0', tags={'alma-mater': 'MIT'})


def test_fingerprint(monkeypatch):
    def fake_response(url, json, **kwargs):
        assert json.get('fingerprint') == ['gordon', 'freeman']
        return httpx.Response(200)

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert sentry.send_event('https://fake@dsn/0', fingerprint=['gordon', 'freeman'])


def test_message(monkeypatch):
    def fake_response(url, json, **kwargs):
        assert json.get('message') == 'Rise and shine, Mr. Freeman'
        return httpx.Response(200)

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert sentry.send_event('https://fake@dsn/0', message='Rise and shine, Mr. Freeman')


def test_appid(monkeypatch):
    def fake_response(url, json, **kwargs):
        assert json.get('fingerprint') == ['appid:1234']
        assert json.get('tags') == {'appid': '1234'}
        return httpx.Response(200)

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert sentry.send_event('https://fake@dsn/0', appid=1234)


def test_appid_fingerprint_dupe(monkeypatch):
    def fake_response(url, json, **kwargs):
        assert json.get('fingerprint') == ['appid:1234']
        assert json.get('tags') == {'appid': '1234'}
        return httpx.Response(200)

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert sentry.send_event('https://fake@dsn/0', appid=1234, fingerprint=['appid:1234'])


def test_appid_tag_dupe(monkeypatch):
    def fake_response(url, json, **kwargs):
        assert json.get('fingerprint') == ['appid:1234']
        assert json.get('tags') == {'appid': '1234'}
        return httpx.Response(200)

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert sentry.send_event('https://fake@dsn/0', appid=1234, tags={'appid': '4321'})


def test_envelope(monkeypatch):
    event_id = None

    def fake_response(url, **kwargs):
        nonlocal event_id
        if url == 'https://fake@dsn/api/0/store/':
            event_id = kwargs['json']['event_id']
        elif url == 'https://fake@dsn/api/0/envelope/':
            data = gzip.decompress(kwargs['data'])
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

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert sentry.send_event('https://fake@dsn/0', attachments=[{
        'data': b'headcrab zombie',
        'filename': 'enemy.txt',
        'mime-type': 'text/plain',
    }])


def test_envelope_multiple_attachments(monkeypatch):
    event_id = None

    def fake_response(url, **kwargs):
        nonlocal event_id
        if url == 'https://fake@dsn/api/0/store/':
            pass
        elif url == 'https://fake@dsn/api/0/envelope/':
            data = gzip.decompress(kwargs['data'])
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

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert sentry.send_event('https://fake@dsn/0', attachments=[
        {
            'data': b'crowbar',
        },
        {
            'data': b'gravity gun',
        }
    ])


def test_envelope_timestamp(monkeypatch):
    def fake_response(url, **kwargs):
        if url == 'https://fake@dsn/api/0/store/':
            assert kwargs['json']['timestamp'] == 0.0
        elif url == 'https://fake@dsn/api/0/envelope/':
            data = gzip.decompress(kwargs['data'])
            line, data = data.split(b'\n', 1)
            header = json.loads(line)
            assert isinstance(header.get('sent_at'), str)
        else:
            assert False
        return httpx.Response(200)

    monkeypatch.setattr(httpx, 'post', fake_response)
    assert sentry.send_event('https://fake@dsn/0', timestamp=0.0, attachments=[{'data': b''}])
