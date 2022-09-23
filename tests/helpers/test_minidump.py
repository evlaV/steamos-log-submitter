import builtins
import requests
import steamos_log_submitter.helpers.minidump as helper
import steamos_log_submitter.util as util
from .. import open_shim


def test_submit_bad_name():
    assert not helper.submit('not-a-dmp.txt')


def test_submit_metadata(monkeypatch):
    def post(*args, **kwargs):
        data = kwargs['data']
        assert data.get('sentry[tags][steam_id]') == 123
        assert data.get('sentry[tags][appid]') == 456
        assert data.get('sentry[tags][build_id]') == '20220202.202'
        r = requests.Response()
        r.status_code = 200
        return r

    monkeypatch.setattr(util, 'get_steam_account_id', lambda: 123)
    monkeypatch.setattr(util, 'get_build_id', lambda: '20220202.202')
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(builtins, 'open', open_shim('MDMP'))

    assert helper.submit('fake-0-456.dmp')


def test_no_metadata(monkeypatch):
    def post(*args, **kwargs):
        data = kwargs['data']
        assert 'sentry[tags][steam_id]' not in data
        assert 'sentry[tags][appid]' not in data
        assert 'sentry[tags][build_id]' not in data
        r = requests.Response()
        r.status_code = 200
        return r

    monkeypatch.setattr(util, 'get_steam_account_id', lambda: None)
    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(builtins, 'open', open_shim('MDMP'))

    assert helper.submit('fake.dmp')
