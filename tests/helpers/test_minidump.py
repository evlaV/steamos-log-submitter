# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import httpx
import json
import os
import pytest
import tempfile
import steamos_log_submitter.util as util
from steamos_log_submitter.helpers import HelperResult
from steamos_log_submitter.helpers.minidump import MinidumpHelper as helper
from .. import custom_dsn
from .. import mock_config, open_shim  # NOQA: F401

dsn = custom_dsn('helpers.minidump')


@pytest.mark.asyncio
async def test_submit_metadata(monkeypatch, open_shim):
    async def post(*args, **kwargs):
        data = json.loads(kwargs['data']['sentry'])
        assert data.get('tags', {}).get('unit_id') == 'unit'
        assert data.get('tags', {}).get('appid') == 456
        assert data.get('tags', {}).get('product') == 'Valve'
        assert data.get('release') == '20220202.202'
        assert data.get('environment') == 'rel'
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: '20220202.202')
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: 'unit')
    monkeypatch.setattr(util, 'get_steamos_branch', lambda: 'rel')
    monkeypatch.setattr(util, 'read_file', lambda _: 'Valve')
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    open_shim(b'MDMP')

    assert await helper.submit('fake-0-456.dmp') == HelperResult.OK


@pytest.mark.asyncio
async def test_no_metadata(monkeypatch, open_shim):
    async def post(*args, **kwargs):
        data = json.loads(kwargs['data']['sentry'])
        assert 'unit_id' not in data.get('tags', {})
        assert 'appid' not in data.get('tags', {})
        assert 'product' not in data.get('tags', {})
        assert 'executable' not in data.get('tags', {})
        assert 'comm' not in data.get('tags', {})
        assert 'path' not in data.get('tags', {})
        assert 'release' not in data
        assert 'environment' not in data
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: None)
    monkeypatch.setattr(util, 'get_steamos_branch', lambda: None)
    monkeypatch.setattr(util, 'read_file', lambda _: None)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    open_shim(b'MDMP')

    assert await helper.submit('fake.dmp') == HelperResult.OK


@pytest.mark.asyncio
async def test_no_xattrs(monkeypatch):
    async def post(*args, **kwargs):
        data = json.loads(kwargs['data']['sentry'])
        assert data.get('tags', {}).get('executable') == 'exe'
        assert data.get('tags', {}).get('comm') == 'comm'
        assert data.get('tags', {}).get('path') == '/fake/exe'
        assert data.get('fingerprint') == ['executable:exe']
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: None)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)

    mdmp = tempfile.NamedTemporaryFile(suffix='.dmp', dir=os.getcwd())  # tmpfs doesn't support user xattrs for some reason
    mdmp.write(b'MDMP')
    os.setxattr(mdmp.name, 'user.executable', b'exe')
    os.setxattr(mdmp.name, 'user.comm', b'comm')
    os.setxattr(mdmp.name, 'user.path', b'/fake/exe')

    assert await helper.submit(mdmp.name) == HelperResult.OK


@pytest.mark.asyncio
async def test_partial_xattrs(monkeypatch):
    async def post(*args, **kwargs):
        data = json.loads(kwargs['data']['sentry'])
        assert data.get('tags', {}).get('executable') == 'exe'
        assert 'comm' not in data.get('tags', {})
        assert data.get('tags', {}).get('path') == '/fake/exe'
        assert data.get('fingerprint') == ['executable:exe']
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: None)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)

    mdmp = tempfile.NamedTemporaryFile(suffix='.dmp', dir=os.getcwd())  # tmpfs doesn't support user xattrs for some reason
    mdmp.write(b'MDMP')
    os.setxattr(mdmp.name, 'user.executable', b'exe')
    os.setxattr(mdmp.name, 'user.path', b'/fake/exe')

    assert await helper.submit(mdmp.name) == HelperResult.OK


@pytest.mark.asyncio
async def test_400_corrupted(monkeypatch, open_shim):
    async def post(*args, **kwargs):
        return httpx.Response(400, content=b'{"detail":"invalid minidump"}')

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: None)
    monkeypatch.setattr(util, 'read_file', lambda _: None)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    open_shim(b'MDMP')

    assert await helper.submit('fake.dmp') == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_400_not_corrupted(monkeypatch, open_shim):
    async def post(*args, **kwargs):
        return httpx.Response(400)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(util, 'telemetry_unit_id', lambda: None)
    monkeypatch.setattr(util, 'read_file', lambda _: None)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    open_shim(b'MDMP')

    assert await helper.submit('fake.dmp') == HelperResult.TRANSIENT_ERROR
