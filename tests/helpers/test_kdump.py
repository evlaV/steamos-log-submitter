import json
import os
import requests
import steamos_log_submitter.crash as crash
import steamos_log_submitter.helpers.kdump as kdump

file_base = f'{os.path.dirname(__file__)}/kdump'

def test_dmesg_parse():
    with open(f'{file_base}/crash') as f:
        crash_expected = f.read()
    with open(f'{file_base}/stack') as f:
        stack_expected = f.read()
    with open(f'{file_base}/dmesg') as f:
        crash, stack = kdump.get_summaries(f)
    assert crash == crash_expected
    assert stack == stack_expected


def test_submit_bad_name():
    assert not kdump.submit('not-a-zip.txt')


def test_submit_succeed(monkeypatch):
    attempt = 0
    def fake_response(body):
        def ret(url, data=None, *args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
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
    respond = fake_response(response)
    monkeypatch.setattr(requests, 'post', respond)
    monkeypatch.setattr(requests, 'put', respond)
    assert kdump.submit(f'{file_base}/dmesg.zip')
    assert attempt == 3


def test_submit_empty(monkeypatch):
    monkeypatch.setattr(crash, 'upload', lambda **kwargs: False)
    assert not kdump.submit(f'{file_base}/empty.zip')


def test_submit_bad_zip(monkeypatch):
    monkeypatch.setattr(crash, 'upload', lambda **kwargs: False)
    assert not kdump.submit(f'{file_base}/bad.zip')


def test_collect_none():
    assert not kdump.collect()

# vim:ts=4:sw=4:et
