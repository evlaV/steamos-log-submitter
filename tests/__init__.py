# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
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
    def open_fake(fname, mode='r'):
        if text is None:
            raise FileNotFoundError
        if 'b' in mode:
            return io.BytesIO(text)
        else:
            return io.StringIO(text)
    return open_fake


def open_shim_cb(cb):
    def open_fake(fname, *args):
        text = cb(fname)
        if text is None:
            raise FileNotFoundError
        return io.StringIO(text)
    return open_fake


def open_enoent(fname, *args, **kwargs):
    raise FileNotFoundError(fname)


def open_eacces(fname, *args, **kwargs):
    raise PermissionError(fname)


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


def always_raise(exc):
    def ret(*args, **kwargs):
        raise exc
    return ret


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
        if name.startswith('steamos_log_submitter.helpers.test'):
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


class HitCounter:
    def __init__(self, ret=None, exc=None):
        self.hits = 0
        self.ret = ret
        self.exc = exc

    def __call__(self, *args, **kwargs):
        self.hits += 1
        if self.exc:
            raise self.exc
        return self.ret


@pytest.fixture
def count_hits():
    return HitCounter()
