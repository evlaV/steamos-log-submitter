# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import pytest
import steamos_log_submitter.sentry as sentry
from steamos_log_submitter.helpers import create_helper, HelperResult
from .. import custom_dsn, unreachable
from .. import mock_config, open_shim  # NOQA: F401

dsn = custom_dsn('helpers.gpu')
helper = create_helper('gpu')


@pytest.mark.asyncio
async def test_collect_none():
    assert not await helper.collect()


@pytest.mark.asyncio
async def test_bad_file(monkeypatch, open_shim):
    monkeypatch.setattr(sentry, 'send_event', unreachable)
    open_shim(b'!')

    assert (await helper.submit('fake.json')).code == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_no_timestamp(monkeypatch, open_shim):
    hit = False

    async def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['timestamp'] is None
        return True

    monkeypatch.setattr(sentry, 'send_event', check_now)
    open_shim(b'{}')

    assert (await helper.submit('fake.json')).code == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_bad_timestamp(monkeypatch, open_shim):
    hit = False

    async def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['timestamp'] is None
        return True

    monkeypatch.setattr(sentry, 'send_event', check_now)
    open_shim(b'{"timestamp":"fake"}')

    assert (await helper.submit('fake.json')).code == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_timestamp(monkeypatch, open_shim):
    hit = False

    async def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['timestamp'] == 1234
        return True

    monkeypatch.setattr(sentry, 'send_event', check_now)
    open_shim(b'{"timestamp":1234.0}')

    assert (await helper.submit('fake.json')).code == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_no_appid(monkeypatch, open_shim):
    hit = False

    async def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['appid'] is None
        assert kwargs['message'] == 'GPU reset'
        return True

    monkeypatch.setattr(sentry, 'send_event', check_now)
    open_shim(b'{}')

    assert (await helper.submit('fake.json')).code == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_bad_appid(monkeypatch, open_shim):
    hit = False

    async def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['appid'] is None
        assert kwargs['message'] == 'GPU reset'
        return True

    monkeypatch.setattr(sentry, 'send_event', check_now)
    open_shim(b'{"appid":null}')

    assert (await helper.submit('fake.json')).code == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_appid(monkeypatch, open_shim):
    hit = False

    async def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['appid'] == 1234
        assert kwargs['message'] == 'GPU reset (1234)'
        return True

    monkeypatch.setattr(sentry, 'send_event', check_now)
    open_shim(b'{"appid":1234}')

    assert (await helper.submit('fake.json')).code == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_exe(monkeypatch, open_shim):
    hit = False

    async def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['tags']['executable'] == 'hl2.exe'
        assert 'executable:hl2.exe' in kwargs['fingerprint']
        assert kwargs['message'] == 'GPU reset (hl2.exe)'
        return True

    monkeypatch.setattr(sentry, 'send_event', check_now)
    open_shim(b'{"executable":"hl2.exe"}')

    assert (await helper.submit('fake.json')).code == HelperResult.OK
    assert hit


@pytest.mark.asyncio
async def test_kernel(monkeypatch, open_shim):
    hit = False

    async def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['tags']['kernel'] == '4.20.69-valve1'
        assert 'kernel:4.20.69-valve1' in kwargs['fingerprint']
        return True

    monkeypatch.setattr(sentry, 'send_event', check_now)
    open_shim(b'{"kernel":"4.20.69-valve1"}')

    assert (await helper.submit('fake.json')).code == HelperResult.OK
    assert hit
