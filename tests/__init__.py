# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import configparser
import httpx
import importlib
import io
import os
import pwd
import pytest
import tempfile
import steamos_log_submitter as sls
import steamos_log_submitter.helpers
from collections.abc import Awaitable, Callable
from typing import Any


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
        return httpx.Response(status_code)
    return ret


def fake_response(body):
    def ret(*args, **kwargs):
        return httpx.Response(200, content=body.encode())
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
        defaults = None

        @classmethod
        def _setup(cls):
            pass
    return FakeModule()


@pytest.fixture
def helper_directory(monkeypatch, patch_module):
    d = tempfile.TemporaryDirectory(prefix='sls-')
    pending = f'{d.name}/pending'
    uploaded = f'{d.name}/uploaded'
    failed = f'{d.name}/failed'
    os.mkdir(pending)
    os.mkdir(uploaded)
    os.mkdir(failed)
    monkeypatch.setattr(sls, 'pending', pending)
    monkeypatch.setattr(sls, 'uploaded', uploaded)
    monkeypatch.setattr(sls, 'failed', failed)

    original_import_module = importlib.import_module

    def import_module(name, package=None):
        if name.startswith('steamos_log_submitter.helpers.test'):
            patch_module.helper = patch_module
            return patch_module
        return original_import_module(name, package)
    monkeypatch.setattr(importlib, 'import_module', import_module)

    def list_helpers():
        nonlocal d
        return list(os.listdir(f'{d.name}/pending'))
    monkeypatch.setattr(steamos_log_submitter.helpers, 'list_helpers', list_helpers)

    yield d.name

    del d


def setup_categories(categories):
    for category in categories:
        os.mkdir(f'{sls.pending}/{category}')
        os.mkdir(f'{sls.uploaded}/{category}')
        os.mkdir(f'{sls.failed}/{category}')


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


@pytest.fixture
def data_directory(monkeypatch):
    d = tempfile.TemporaryDirectory(prefix='sls-')
    monkeypatch.setattr(sls.data, 'data_root', d.name)
    for dat in sls.data.datastore.values():
        monkeypatch.setattr(dat, '_data', {})
        monkeypatch.setattr(dat, '_dirty', False)
    yield d.name

    del d


@pytest.fixture
def drop_root():
    if os.geteuid() != 0:
        yield
    else:
        with sls.util.drop_root('nobody', 'nobody'):
            yield


def custom_dsn(section: str, dsn: str = ''):
    @pytest.fixture(autouse=True)
    def dsn_fixture(mock_config):
        mock_config.add_section(section)
        mock_config.set(section, 'dsn', dsn)

    return dsn_fixture


def awaitable(fn: Callable[..., Any]) -> Awaitable[Any]:
    async def afn(*args, **kwargs):
        return fn(*args, **kwargs)

    return afn
