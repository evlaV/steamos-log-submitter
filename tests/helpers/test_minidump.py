# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import os
import requests
import tempfile
import steamos_log_submitter.helpers.minidump as helper
import steamos_log_submitter.util as util
from .. import open_shim


def test_submit_bad_name():
    assert not helper.submit('not-a-dmp.txt')


def test_submit_metadata(monkeypatch):
    def post(*args, **kwargs):
        data = kwargs['data']
        assert data.get('sentry[tags][appid]') == 456
        assert data.get('sentry[tags][build_id]') == '20220202.202'
        r = requests.Response()
        r.status_code = 200
        return r

    monkeypatch.setattr(util, 'get_build_id', lambda: '20220202.202')
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(builtins, 'open', open_shim(b'MDMP'))

    assert helper.submit('fake-0-456.dmp')


def test_no_metadata(monkeypatch):
    def post(*args, **kwargs):
        data = kwargs['data']
        assert 'sentry[tags][appid]' not in data
        assert 'sentry[tags][build_id]' not in data
        assert 'sentry[tags][executable]' not in data
        assert 'sentry[tags][comm]' not in data
        assert 'sentry[tags][path]' not in data
        r = requests.Response()
        r.status_code = 200
        return r

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(builtins, 'open', open_shim(b'MDMP'))

    assert helper.submit('fake.dmp')


def test_no_xattrs(monkeypatch):
    def post(*args, **kwargs):
        data = kwargs['data']
        assert data.get('sentry[tags][executable]') == b'exe'
        assert data.get('sentry[tags][comm]') == b'comm'
        assert data.get('sentry[tags][path]') == b'/fake/exe'
        r = requests.Response()
        r.status_code = 200
        return r

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(requests, 'post', post)

    mdmp = tempfile.NamedTemporaryFile(suffix='.dmp', dir=os.getcwd())  # tmpfs doesn't support user xattrs for some reason
    mdmp.write(b'MDMP')
    os.setxattr(mdmp.name, 'user.executable', b'exe')
    os.setxattr(mdmp.name, 'user.comm', b'comm')
    os.setxattr(mdmp.name, 'user.path', b'/fake/exe')

    assert helper.submit(mdmp.name)


def test_partial_xattrs(monkeypatch):
    def post(*args, **kwargs):
        data = kwargs['data']
        assert data.get('sentry[tags][executable]') == b'exe'
        assert 'sentry[tags][comm]' not in data
        assert data.get('sentry[tags][path]') == b'/fake/exe'
        r = requests.Response()
        r.status_code = 200
        return r

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(requests, 'post', post)

    mdmp = tempfile.NamedTemporaryFile(suffix='.dmp', dir=os.getcwd())  # tmpfs doesn't support user xattrs for some reason
    mdmp.write(b'MDMP')
    os.setxattr(mdmp.name, 'user.executable', b'exe')
    os.setxattr(mdmp.name, 'user.path', b'/fake/exe')

    assert helper.submit(mdmp.name)


def test_400_corrupted(monkeypatch):
    def post(*args, **kwargs):
        r = requests.Response()
        r._content = b'{"detail":"invalid minidump"}'
        r.status_code = 400
        return r

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(builtins, 'open', open_shim(b'MDMP'))

    assert helper.submit('fake.dmp')


def test_400_not_corrupted(monkeypatch):
    def post(*args, **kwargs):
        r = requests.Response()
        r.status_code = 400
        return r

    monkeypatch.setattr(util, 'get_build_id', lambda: None)
    monkeypatch.setattr(requests, 'post', post)
    monkeypatch.setattr(builtins, 'open', open_shim(b'MDMP'))

    assert not helper.submit('fake.dmp')
