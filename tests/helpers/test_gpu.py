# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import pytest
import steamos_log_submitter.aggregators.sentry as sentry
from steamos_log_submitter.helpers import HelperResult
from steamos_log_submitter.helpers.gpu import GPUHelper as helper
from .. import custom_dsn, unreachable
from .. import mock_config, open_shim  # NOQA: F401

dsn = custom_dsn('helpers.gpu')


@pytest.mark.asyncio
async def test_collect_none():
    assert not await helper.collect()


@pytest.mark.asyncio
async def test_bad_file(monkeypatch, open_shim):
    monkeypatch.setattr(sentry.SentryEvent, 'send', unreachable)
    open_shim(b'!')

    assert await helper.submit('fake.json') == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_no_timestamp(monkeypatch, open_shim):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.timestamp is None
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    open_shim(b'{}')

    assert await helper.submit('fake.json') == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_bad_timestamp(monkeypatch, open_shim):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.timestamp is None
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    open_shim(b'{"timestamp":"fake"}')

    assert await helper.submit('fake.json') == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_timestamp(monkeypatch, open_shim):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.timestamp == 1234
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    open_shim(b'{"timestamp":1234.0}')

    assert await helper.submit('fake.json') == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_no_appid(monkeypatch, open_shim):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.appid is None
        assert self.message == 'GPU reset'
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    open_shim(b'{}')

    assert await helper.submit('fake.json') == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_bad_appid(monkeypatch, open_shim):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.appid is None
        assert self.message == 'GPU reset'
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    open_shim(b'{"appid":null}')

    assert await helper.submit('fake.json') == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_appid(monkeypatch, open_shim):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.appid == 1234
        assert self.message == 'GPU reset (1234)'
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    open_shim(b'{"appid":1234}')

    assert await helper.submit('fake.json') == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_exe(monkeypatch, open_shim):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.tags['executable'] == 'hl2.exe'
        assert 'executable:hl2.exe' in self.fingerprint
        assert self.message == 'GPU reset (hl2.exe)'
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    open_shim(b'{"executable":"hl2.exe"}')

    assert await helper.submit('fake.json') == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_comm(monkeypatch, open_shim):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.tags['comm'] == 'hl2'
        assert 'comm:hl2' in self.fingerprint
        assert self.message == 'GPU reset (hl2)'
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    open_shim(b'{"comm":"hl2"}')

    assert await helper.submit('fake.json') == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_kernel(monkeypatch, open_shim):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.tags['kernel'] == '4.20.69-valve1'
        assert 'kernel:4.20.69-valve1' in self.fingerprint
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    open_shim(b'{"kernel":"4.20.69-valve1"}')

    assert await helper.submit('fake.json') == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_mesa(monkeypatch, open_shim):
    hit = False

    async def check_now(self):
        nonlocal hit
        hit = True
        assert self.tags['mesa'] == '23.1.3.170235.radeonsi_3.5.1-1'
        assert 'mesa:23.1.3.170235.radeonsi_3.5.1-1' in self.fingerprint
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    open_shim(b'{"mesa":"23.1.3.170235.radeonsi_3.5.1-1"}')

    assert await helper.submit('fake.json') == HelperResult.OK
    assert hit
