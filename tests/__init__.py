# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import builtins
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
from collections.abc import Callable, Coroutine
from typing import Optional, ParamSpec, TypeVar, Union

P = ParamSpec('P')
T = TypeVar('T')


@pytest.fixture
def open_shim(monkeypatch):
    class OpenShim:
        @staticmethod
        def __call__(text):
            def open_fake(fname, mode='r', *args, **kwargs):
                if text is None:
                    raise FileNotFoundError
                if 'b' in mode:
                    return io.BytesIO(text)
                else:
                    return io.StringIO(text)
            monkeypatch.setattr(builtins, 'open', open_fake)

        @staticmethod
        def cb(cb):
            def open_fake(fname, mode='r', *args, **kwargs):
                text = cb(fname)
                if text is None:
                    raise FileNotFoundError
                if 'b' in mode:
                    return io.BytesIO(text)
                else:
                    return io.StringIO(text)
            monkeypatch.setattr(builtins, 'open', open_fake)

        @staticmethod
        def do_raise(exc):
            def open_fake(fname, *args, **kwargs):
                raise exc(fname)
            monkeypatch.setattr(builtins, 'open', open_fake)

        @classmethod
        def enoent(cls):
            cls.do_raise(FileNotFoundError)

        @classmethod
        def eacces(cls):
            cls.do_raise(PermissionError)

    return OpenShim()


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
def patch_module(mock_config, monkeypatch):
    class TestHelper(sls.helpers.Helper):
        defaults = None

        @classmethod
        def _setup(cls):
            cls.iface = sls.helpers.HelperInterface(cls)

    TestHelper.name = 'test'
    TestHelper.config = sls.config.get_config('steamos_log_submitter.helpers.test')

    original_import_module = importlib.import_module

    def import_module(name, package=None):
        if name.startswith('steamos_log_submitter.helpers.test'):
            helper_name = name.split('.')[-1]
            if helper_name == 'test':
                TestHelper.helper = TestHelper
                return TestHelper
            else:
                class SubTestHelper(TestHelper):
                    name = helper_name

                SubTestHelper.helper = SubTestHelper
                SubTestHelper.config = sls.config.get_config(name)
                return SubTestHelper
        return original_import_module(name, package)
    monkeypatch.setattr(importlib, 'import_module', import_module)
    monkeypatch.setattr(steamos_log_submitter.helpers, 'list_helpers', lambda: ['test'])

    return TestHelper


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


def setup_logs(helper_directory, logs):
    for fname, text in logs.items():
        with open(f'{sls.pending}/{fname}', 'w') as f:
            if text:
                f.write(text)


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


def awaitable(fn: Callable[P, T]) -> Callable[P, Coroutine[None, None, T]]:
    async def afn(*args, **kwargs):
        return fn(*args, **kwargs)

    return afn


class Popen:
    stdin: Optional[Union[io.BytesIO, io.StringIO]]
    stdout: Optional[Union[io.BytesIO, io.StringIO]]
    stderr: Optional[Union[io.BytesIO, io.StringIO]]
    wait: Callable[[Optional[int]], None]
    returncode: Optional[int]

    def wait(self, timeout: Optional[int] = None) -> None:  # type: ignore[no-redef]
        pass

    def __init__(self, *,
                 stdin: Optional[Union[io.BytesIO, io.StringIO]] = None,
                 stdout: Optional[Union[io.BytesIO, io.StringIO]] = None,
                 stderr: Optional[Union[io.BytesIO, io.StringIO]] = None,
                 returncode: Optional[int] = None,
                 wait: Callable[[Optional[int]], None] = wait):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.wait = wait


@pytest.fixture
def fake_async_subprocess(monkeypatch):
    def setup(*, stdout=None, stderr=None, returncode=0):
        async def fake_subprocess(*args, **kwargs):
            ret = Popen(returncode=returncode)
            if stdout:
                ret.stdout = io.BytesIO(stdout)
                ret.stdout.read = awaitable(ret.stdout.read)  # type: ignore[assignment]
                ret.stdout.readline = awaitable(ret.stdout.readline)  # type: ignore[assignment]
            if stderr:
                ret.stderr = io.BytesIO(stderr)
                ret.stderr.read = awaitable(ret.stderr.read)  # type: ignore[assignment]
                ret.stderr.readline = awaitable(ret.stderr.readline)  # type: ignore[assignment]
            return ret
        monkeypatch.setattr(asyncio, 'create_subprocess_exec', fake_subprocess)

    return setup


class CustomConfig:
    def __init__(self, monkeypatch):
        self.base_file = tempfile.NamedTemporaryFile(suffix='.cfg', mode='w+')
        self.user_file = tempfile.NamedTemporaryFile(suffix='.cfg', mode='w+')
        self.local_file = tempfile.NamedTemporaryFile(suffix='.cfg', mode='w+')
        monkeypatch.setattr(sls.config, 'base_config_path', self.base_file.name)
        monkeypatch.setattr(sls.config, 'config', None)
        monkeypatch.setattr(sls.config, 'local_config', configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation()))
        self.base = configparser.ConfigParser()
        self.base.add_section('sls')
        self.base.set('sls', 'user-config', self.user_file.name)
        self.base.set('sls', 'local-config', self.local_file.name)
        self.user = configparser.ConfigParser()
        self.local = configparser.ConfigParser()

    def write(self):
        self.base.write(self.base_file)
        self.base_file.flush()

        self.user.write(self.user_file)
        self.user_file.flush()

        self.local.write(self.local_file)
        self.local_file.flush()
