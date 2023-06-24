# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import steamos_log_submitter.helpers.gpu as helper
from .. import open_shim
from .. import mock_config  # NOQA: F401


def test_submit_bad_name():
    assert not helper.submit('not-a-log.bin')


def test_collect_none():
    assert not helper.collect()


def test_no_timestamp(mock_config, monkeypatch):
    hit = False
    mock_config.add_section('helpers.gpu')
    mock_config.set('helpers.gpu', 'dsn', '')

    def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['timestamp'] is None
        return True

    monkeypatch.setattr(helper, 'send_event', check_now)
    monkeypatch.setattr(builtins, 'open', open_shim(b''))

    assert helper.submit('fake.log')
    assert hit


def test_bad_timestamp(mock_config, monkeypatch):
    hit = False
    mock_config.add_section('helpers.gpu')
    mock_config.set('helpers.gpu', 'dsn', '')

    def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['timestamp'] is None
        return True

    monkeypatch.setattr(helper, 'send_event', check_now)
    monkeypatch.setattr(builtins, 'open', open_shim(b'A=0\nTIMESTAMP=fake\nB=1\n'))

    assert helper.submit('fake.log')
    assert hit


def test_timestamp(mock_config, monkeypatch):
    hit = False
    mock_config.add_section('helpers.gpu')
    mock_config.set('helpers.gpu', 'dsn', '')

    def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['timestamp'] == 1234
        return True

    monkeypatch.setattr(helper, 'send_event', check_now)
    monkeypatch.setattr(builtins, 'open', open_shim(b'A=0\nTIMESTAMP=1234000000000\nB=1\n'))

    assert helper.submit('fake.log')
    assert hit


def test_no_appid(mock_config, monkeypatch):
    hit = False
    mock_config.add_section('helpers.gpu')
    mock_config.set('helpers.gpu', 'dsn', '')

    def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['appid'] is None
        return True

    monkeypatch.setattr(helper, 'send_event', check_now)
    monkeypatch.setattr(builtins, 'open', open_shim(b''))

    assert helper.submit('fake.log')
    assert hit


def test_bad_appid(mock_config, monkeypatch):
    hit = False
    mock_config.add_section('helpers.gpu')
    mock_config.set('helpers.gpu', 'dsn', '')

    def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['appid'] is None
        return True

    monkeypatch.setattr(helper, 'send_event', check_now)
    monkeypatch.setattr(builtins, 'open', open_shim(b'A=0\nAPPID=None\nB=1\n'))

    assert helper.submit('fake.log')
    assert hit


def test_appid(mock_config, monkeypatch):
    hit = False
    mock_config.add_section('helpers.gpu')
    mock_config.set('helpers.gpu', 'dsn', '')

    def check_now(dsn, **kwargs):
        nonlocal hit
        hit = True
        assert kwargs['appid'] == 1234
        return True

    monkeypatch.setattr(helper, 'send_event', check_now)
    monkeypatch.setattr(builtins, 'open', open_shim(b'A=0\nAPPID=1234\nB=1\n'))

    assert helper.submit('fake.log')
    assert hit
