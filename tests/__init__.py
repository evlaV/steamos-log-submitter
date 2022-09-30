import configparser
import importlib
import io
import os
import pwd
import pytest
import requests
import tempfile
import steamos_log_submitter as sls


def open_shim(text):
    def open_fake(*args):
        return io.StringIO(text)
    return open_fake


def open_shim_cb(cb):
    def open_fake(fname, *args):
        text = cb(fname)
        if text is None:
            raise FileNotFoundError
        return io.StringIO(text)
    return open_fake


def fake_request(status_code):
    def ret(*args, **kwargs):
        r = requests.Response()
        r.status_code = status_code
        return r
    return ret


def fake_response(body):
    def ret(*args, **kwargs):
        r = requests.Response()
        r.status_code = 200
        r._content = body.encode()
        return r
    return ret


def unreachable(*args, **kwargs):
    assert False


@pytest.fixture
def patch_module():
    class FakeModule:
        pass
    return FakeModule()


@pytest.fixture
def helper_directory(monkeypatch, patch_module):
    d = tempfile.TemporaryDirectory(prefix='sls-')
    pending = f'{d.name}/pending'
    uploaded = f'{d.name}/uploaded'
    os.mkdir(pending)
    os.mkdir(uploaded)
    monkeypatch.setattr(sls, 'pending', f'{d.name}/pending')
    monkeypatch.setattr(sls, 'uploaded', f'{d.name}/uploaded')

    original_import_module = importlib.import_module

    def import_module(name, package=None):
        if name == 'steamos_log_submitter.helpers.test':
            return patch_module
        return original_import_module(name, package)
    monkeypatch.setattr(importlib, 'import_module', import_module)

    yield d.name

    del d


def setup_categories(categories):
    for category in categories:
        os.mkdir(f'{sls.pending}/{category}')
        os.mkdir(f'{sls.uploaded}/{category}')


@pytest.fixture
def mock_config(monkeypatch):
    testconf = configparser.ConfigParser()
    monkeypatch.setattr(sls.config, 'config', testconf)
    monkeypatch.setattr(sls.config, 'local_config', testconf)
    monkeypatch.setattr(sls.config, 'write_config', lambda: None)
    return testconf


@pytest.fixture(autouse=True)
def fake_pwuid(monkeypatch):
    def getpwuid(uid):
        return pwd.struct_passwd(['', '', uid, uid, '', f'/home/{uid}', ''])
    monkeypatch.setattr(pwd, 'getpwuid', getpwuid)

# vim:ts=4:sw=4:et
