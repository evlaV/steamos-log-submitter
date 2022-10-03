# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import os
import time
import steamos_log_submitter.helpers.gpu as helper
from .crash import FakeResponse
from .. import open_shim


def test_submit_bad_name():
    assert not helper.submit('not-a-log.bin')


def test_collect_none():
    assert not helper.collect()


def test_no_timestamp(monkeypatch):
    hit = False

    def check_now(info, **kwargs):
        nonlocal hit
        hit = True
        timestamp = info['crash_time']
        now = time.time()
        assert (now - timestamp) < 100_000_000  # 100ms tolerance
        return True

    monkeypatch.setattr(helper, 'upload_crash', check_now)
    monkeypatch.setattr(builtins, 'open', open_shim(''))

    assert helper.submit('fake.log')
    assert hit


def test_bad_timestamp(monkeypatch):
    hit = False

    def check_now(info, **kwargs):
        nonlocal hit
        hit = True
        timestamp = info['crash_time']
        now = time.time()
        assert (now - timestamp) < 100_000_000  # 100ms tolerance
        return True

    monkeypatch.setattr(helper, 'upload_crash', check_now)
    monkeypatch.setattr(builtins, 'open', open_shim('A=0\nTIMESTAMP=fake\nB=1\n'))

    assert helper.submit('fake.log')
    assert hit


def test_timestamp(monkeypatch):
    hit = False

    def check_now(info, **kwargs):
        nonlocal hit
        hit = True
        assert info['crash_time'] == 1234
        return True

    monkeypatch.setattr(helper, 'upload_crash', check_now)
    monkeypatch.setattr(builtins, 'open', open_shim('A=0\nTIMESTAMP=1234000000000\nB=1\n'))

    assert helper.submit('fake.log')
    assert hit
