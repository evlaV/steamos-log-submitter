# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import httpx
import os
import tempfile
import steamos_log_submitter.util as util
import steamos_log_submitter.steam as steam
from steamos_log_submitter.helpers import create_helper, HelperResult
from .. import custom_dsn, open_shim
from .. import mock_config  # NOQA: F401

dsn = custom_dsn('helpers.minidump')
helper = create_helper('minidump')


def test_submit_bad_name():
    assert helper.submit('not-a-dmp.txt').code == HelperResult.PERMANENT_ERROR


def test_submit_metadata(monkeypatch):
    def post(*args, **kwargs):
        data = kwargs['data']
        assert data.get('sentry[tags][appid]') == 456
        assert data.get('sentry[tags][build_id]') == '20220202.202'
        assert data.get('sentry[environment]') == 'rel'
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: '20220202.202')
    monkeypatch.setattr(steam, 'get_steamos_branch', lambda: 'rel')
    monkeypatch.setattr(httpx, 'post', post)
    monkeypatch.setattr(builtins, 'open', open_shim(b'MDMP'))

    assert helper.submit('fake-0-456.dmp').code == HelperResult.OK


def test_no_metadata(monkeypatch):
    def post(*args, **kwargs):
        data = kwargs['data']
        assert 'sentry[tags][appid]' not in data
        assert 'sentry[tags][build_id]' not in data
        assert 'sentry[tags][executable]' not in data
        assert 'sentry[tags][comm]' not in data
        assert 'sentry[tags][path]' not in data
        assert 'sentry[environment]' not in data
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(steam, 'get_steamos_branch', lambda: None)
    monkeypatch.setattr(httpx, 'post', post)
    monkeypatch.setattr(builtins, 'open', open_shim(b'MDMP'))

    assert helper.submit('fake.dmp').code == HelperResult.OK


def test_no_xattrs(monkeypatch):
    def post(*args, **kwargs):
        data = kwargs['data']
        assert data.get('sentry[tags][executable]') == b'exe'
        assert data.get('sentry[tags][comm]') == b'comm'
        assert data.get('sentry[tags][path]') == b'/fake/exe'
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(httpx, 'post', post)

    mdmp = tempfile.NamedTemporaryFile(suffix='.dmp', dir=os.getcwd())  # tmpfs doesn't support user xattrs for some reason
    mdmp.write(b'MDMP')
    os.setxattr(mdmp.name, 'user.executable', b'exe')
    os.setxattr(mdmp.name, 'user.comm', b'comm')
    os.setxattr(mdmp.name, 'user.path', b'/fake/exe')

    assert helper.submit(mdmp.name).code == HelperResult.OK


def test_partial_xattrs(monkeypatch):
    def post(*args, **kwargs):
        data = kwargs['data']
        assert data.get('sentry[tags][executable]') == b'exe'
        assert 'sentry[tags][comm]' not in data
        assert data.get('sentry[tags][path]') == b'/fake/exe'
        return httpx.Response(200)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(httpx, 'post', post)

    mdmp = tempfile.NamedTemporaryFile(suffix='.dmp', dir=os.getcwd())  # tmpfs doesn't support user xattrs for some reason
    mdmp.write(b'MDMP')
    os.setxattr(mdmp.name, 'user.executable', b'exe')
    os.setxattr(mdmp.name, 'user.path', b'/fake/exe')

    assert helper.submit(mdmp.name).code == HelperResult.OK


def test_400_corrupted(monkeypatch):
    def post(*args, **kwargs):
        return httpx.Response(400, content=b'{"detail":"invalid minidump"}')

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(httpx, 'post', post)
    monkeypatch.setattr(builtins, 'open', open_shim(b'MDMP'))

    assert helper.submit('fake.dmp').code == HelperResult.PERMANENT_ERROR


def test_400_not_corrupted(monkeypatch):
    def post(*args, **kwargs):
        return httpx.Response(400)

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(httpx, 'post', post)
    monkeypatch.setattr(builtins, 'open', open_shim(b'MDMP'))

    assert helper.submit('fake.dmp').code == HelperResult.TRANSIENT_ERROR
