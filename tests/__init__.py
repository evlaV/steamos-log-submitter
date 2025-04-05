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
from collections.abc import Awaitable, Callable, Coroutine
from typing import Optional, ParamSpec, Type, TypeVar, Union

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

        @staticmethod
        def empty():
            def open_fake(fname: str, mode='r', *args, **kwargs):
                if 'b' in mode:
                    return io.BytesIO()
                return io.StringIO()
            monkeypatch.setattr(builtins, 'open', open_fake)

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
        helper: Type[sls.helpers.Helper]

        @classmethod
        def _setup(cls):
            cls.iface = sls.helpers.HelperInterface(cls)

        @classmethod
        async def submit(cls, fname: str) -> sls.helpers.HelperResult:
            raise NotImplementedError

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
        return list(os.listdir(f'{d.name}/pending'))  # NOQA: F821 # flake8 bug
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
                 stdout: Optional[Union[io.BytesIO, io.StringIO, bytes, str]] = None,
                 stderr: Optional[Union[io.BytesIO, io.StringIO, bytes, str]] = None,
                 returncode: Optional[int] = None,
                 wait: Callable[[Optional[int]], None] = wait):
        self.stdin = stdin
        if isinstance(stdout, bytes):
            stdout = io.BytesIO(stdout)
        if isinstance(stdout, str):
            stdout = io.StringIO(stdout)
        self.stdout = stdout
        if isinstance(stderr, bytes):
            stderr = io.BytesIO(stderr)
        if isinstance(stderr, str):
            stderr = io.StringIO(stderr)
        self.stderr = stderr
        self.returncode = returncode
        self.wait = wait

    def communicate(self) -> tuple[Optional[Union[str, bytes]], Optional[Union[str, bytes]]]:
        return self.stdout.read() if self.stdout else None, self.stderr.read() if self.stderr else None


class Process(Popen):
    stdout: Optional[io.BytesIO]
    stderr: Optional[io.BytesIO]
    wait: Callable[[], Awaitable[None]]  # type: ignore[assignment]

    async def wait(self) -> None:  # type: ignore[no-redef,override]
        pass

    def __init__(self, *,
                 stdin: Optional[Union[io.BytesIO, io.StringIO]] = None,
                 stdout: Optional[Union[io.BytesIO, bytes]] = None,
                 stderr: Optional[Union[io.BytesIO, bytes]] = None,
                 returncode: Optional[int] = None,
                 wait: Callable[[], Awaitable[None]] = wait):
        super().__init__(stdin=stdin, stdout=stdout, stderr=stderr, returncode=returncode)
        if self.stdout:
            self.stdout.read = awaitable(self.stdout.read)  # type: ignore[assignment]
            self.stdout.readline = awaitable(self.stdout.readline)  # type: ignore[assignment]
        if self.stderr:
            self.stderr.read = awaitable(self.stderr.read)  # type: ignore[assignment]
            self.stderr.readline = awaitable(self.stderr.readline)  # type: ignore[assignment]

    async def communicate(self) -> tuple[Optional[bytes], Optional[bytes]]:  # type: ignore[override]
        return await self.stdout.read() if self.stdout else None, await self.stderr.read() if self.stderr else None  # type: ignore[misc]


@pytest.fixture
def fake_async_subprocess(monkeypatch):
    def setup(*, stdout: Optional[bytes] = None, stderr: Optional[bytes] = None, returncode=0):
        async def fake_subprocess(*args, **kwargs):
            return Process(stdout=stdout, stderr=stderr, returncode=returncode)
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


class StringIO(io.StringIO):
    def close(self):
        pass


class BytesIO(io.BytesIO):
    def close(self):
        pass
