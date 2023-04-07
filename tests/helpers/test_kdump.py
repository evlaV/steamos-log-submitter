# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import os
import steamos_log_submitter.crash as crash
import steamos_log_submitter.helpers.kdump as kdump
from .crash import FakeResponse
from .. import fake_pwuid

file_base = f'{os.path.dirname(__file__)}/kdump'


def test_dmesg_parse():
    with open(f'{file_base}/crash') as f:
        crash_expected = f.read()
    with open(f'{file_base}/stack') as f:
        stack_expected = f.read()
    with open(f'{file_base}/dmesg') as f:
        crash, stack = kdump.get_summaries(f)
    assert crash == crash_expected
    assert stack == stack_expected


def test_submit_bad_name():
    assert not kdump.submit('not-a-zip.txt')


def test_submit_succeed(monkeypatch):
    response = FakeResponse()
    response.success(monkeypatch)
    assert kdump.submit(f'{file_base}/dmesg.zip')
    assert response.attempt == 3


def test_submit_empty(monkeypatch):
    monkeypatch.setattr(crash, 'upload', lambda **kwargs: False)
    assert not kdump.submit(f'{file_base}/empty.zip')


def test_submit_bad_zip(monkeypatch):
    monkeypatch.setattr(crash, 'upload', lambda **kwargs: False)
    assert not kdump.submit(f'{file_base}/bad.zip')


def test_collect_none():
    assert not kdump.collect()
