import builtins
import glob
import json
import os
import requests
import steamos_log_submitter.helpers.kdump as kdump
import steamos_log_submitter.util as util
import steamos_log_submitter as sls
from . import open_shim

file_base = f'{os.path.dirname(__file__)}/kdump'

def test_dmesg_parse(monkeypatch):
    with open(f'{file_base}/crash') as f:
        crash_expected = f.read()
    with open(f'{file_base}/stack') as f:
        stack_expected = f.read()
    monkeypatch.setattr(glob, 'glob', lambda x: [f'{file_base}/dmesg'])
    crash, stack = kdump.get_summaries()
    assert crash == crash_expected
    assert stack == stack_expected


def test_get_build_id(monkeypatch):
    os_release = """NAME="SteamOS"
PRETTY_NAME="SteamOS"
ID=holo
BUILD_ID=definitely fake
"""
    monkeypatch.setattr(builtins, 'open', open_shim(os_release))
    assert kdump.get_build_id() == 'definitely fake'


def test_no_get_build_id(monkeypatch):
    os_release = """NAME="SteamOS"
PRETTY_NAME="SteamOS"
ID=holo
"""
    monkeypatch.setattr(builtins, 'open', open_shim(os_release))
    assert kdump.get_build_id() is None


def test_submit_bad_name():
    assert not kdump.submit('not-a-zip.txt')


def test_submit_succeed(monkeypatch):
    attempt = 0
    def fake_response(body, filename):
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
    respond = fake_response(response, 'empty.zip')
    monkeypatch.setattr(requests, 'post', respond)
    monkeypatch.setattr(requests, 'put', respond)
    monkeypatch.setattr(glob, 'glob', lambda x: [f'{file_base}/dmesg'])
    monkeypatch.setattr(util, 'get_deck_serial', lambda: 'SERIAL')
    monkeypatch.setattr(util, 'get_steam_account_id', lambda: 'ACCOUNT')
    assert kdump.submit(f'{file_base}/empty.zip')
    assert attempt == 3


def test_collect_none(monkeypatch):
    monkeypatch.setattr(util, 'get_deck_serial', lambda: 'SERIAL')
    monkeypatch.setattr(util, 'get_steam_account_id', lambda: 'ACCOUNT')
    monkeypatch.setattr(glob, 'glob', lambda x: [])
    assert not kdump.collect()


def test_collect_empty(monkeypatch):
    monkeypatch.setattr(util, 'get_deck_serial', lambda: 'SERIAL')
    monkeypatch.setattr(util, 'get_steam_account_id', lambda: 'ACCOUNT')
    monkeypatch.setattr(glob, 'glob', lambda x: ['blank.zip'])
    monkeypatch.setattr(os, 'stat', lambda x: os.stat_result([0,0,0,0,0,0,0,0,0,0]))
    assert not kdump.collect()


def test_collect_rename(monkeypatch):
    def rename(src, dest):
        assert src == 'blank.zip'
        assert dest == f'{sls.pending}/kdump/steamos-blank_SERIAL-ACCOUNT.zip'

    monkeypatch.setattr(util, 'get_deck_serial', lambda: 'SERIAL')
    monkeypatch.setattr(util, 'get_steam_account_id', lambda: 'ACCOUNT')
    monkeypatch.setattr(glob, 'glob', lambda x: ['blank.zip'])
    monkeypatch.setattr(os, 'stat', lambda x: os.stat_result([0,0,0,0,0,0,1,0,0,0]))
    monkeypatch.setattr(os, 'rename', rename)
    assert kdump.collect()

# vim:ts=4:sw=4:et
