# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import httpx
import os
import pytest
import tempfile
import steamos_log_submitter.util as util
import steamos_log_submitter.steam as steam
from steamos_log_submitter.helpers import HelperResult
from steamos_log_submitter.helpers.minidump import MinidumpHelper as helper
from .. import custom_dsn
from .. import mock_config, open_shim  # NOQA: F401

dsn = custom_dsn('helpers.minidump')


@pytest.mark.asyncio
async def test_submit_metadata(monkeypatch, open_shim):
    async def post(*args, **kwargs):
        data = kwargs['data']
        assert data.get('sentry[tags][unit_id]') == 'unit'
        assert data.get('sentry[tags][user_id]') == 'user'
        assert data.get('sentry[tags][appid]') == '456'
        assert data.get('sentry[release]') == '20220202.202'
        assert data.get('sentry[environment]') == 'rel'
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: '20220202.202')
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: 'unit')
    monkeypatch.setattr(util, 'telemetry_user_id', lambda: 'user')
    monkeypatch.setattr(steam, 'get_steamos_branch', lambda: 'rel')
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    open_shim(b'MDMP')

    assert (await helper.submit('fake-0-456.dmp')).code == HelperResult.OK


@pytest.mark.asyncio
async def test_no_metadata(monkeypatch, open_shim):
    async def post(*args, **kwargs):
        data = kwargs['data']
        assert 'sentry[tags][unit_id]' not in data
        assert 'sentry[tags][user_id]' not in data
        assert 'sentry[tags][appid]' not in data
        assert 'sentry[tags][executable]' not in data
        assert 'sentry[tags][comm]' not in data
        assert 'sentry[tags][path]' not in data
        assert 'sentry[release]' not in data
        assert 'sentry[environment]' not in data
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_user_id', lambda: None)
    monkeypatch.setattr(steam, 'get_steamos_branch', lambda: None)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    open_shim(b'MDMP')

    assert (await helper.submit('fake.dmp')).code == HelperResult.OK


@pytest.mark.asyncio
async def test_no_xattrs(monkeypatch):
    async def post(*args, **kwargs):
        data = kwargs['data']
        assert data.get('sentry[tags][executable]') == 'exe'
        assert data.get('sentry[tags][comm]') == 'comm'
        assert data.get('sentry[tags][path]') == '/fake/exe'
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_user_id', lambda: None)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)

    mdmp = tempfile.NamedTemporaryFile(suffix='.dmp', dir=os.getcwd())  # tmpfs doesn't support user xattrs for some reason
    mdmp.write(b'MDMP')
    os.setxattr(mdmp.name, 'user.executable', b'exe')
    os.setxattr(mdmp.name, 'user.comm', b'comm')
    os.setxattr(mdmp.name, 'user.path', b'/fake/exe')

    assert (await helper.submit(mdmp.name)).code == HelperResult.OK


@pytest.mark.asyncio
async def test_partial_xattrs(monkeypatch):
    async def post(*args, **kwargs):
        data = kwargs['data']
        assert data.get('sentry[tags][executable]') == 'exe'
        assert 'sentry[tags][comm]' not in data
        assert data.get('sentry[tags][path]') == '/fake/exe'
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_user_id', lambda: None)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)

    mdmp = tempfile.NamedTemporaryFile(suffix='.dmp', dir=os.getcwd())  # tmpfs doesn't support user xattrs for some reason
    mdmp.write(b'MDMP')
    os.setxattr(mdmp.name, 'user.executable', b'exe')
    os.setxattr(mdmp.name, 'user.path', b'/fake/exe')

    assert (await helper.submit(mdmp.name)).code == HelperResult.OK


@pytest.mark.asyncio
async def test_400_corrupted(monkeypatch, open_shim):
    async def post(*args, **kwargs):
        return httpx.Response(400, content=b'{"detail":"invalid minidump"}')

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_user_id', lambda: None)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    open_shim(b'MDMP')

    assert (await helper.submit('fake.dmp')).code == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_400_not_corrupted(monkeypatch, open_shim):
    async def post(*args, **kwargs):
        return httpx.Response(400)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_user_id', lambda: None)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    open_shim(b'MDMP')

    assert (await helper.submit('fake.dmp')).code == HelperResult.TRANSIENT_ERROR
