# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import os
import pytest
import steamos_log_submitter.crash as crash
import steamos_log_submitter.steam as steam
from steamos_log_submitter.helpers import create_helper, HelperResult
from .crash import FakeResponse
from .. import awaitable
from .. import fake_pwuid  # NOQA: F401

file_base = f'{os.path.dirname(__file__)}/kdump'
helper = create_helper('kdump')


def test_dmesg_parse():
    with open(f'{file_base}/crash') as f:
        crash_expected = f.read()
    with open(f'{file_base}/stack') as f:
        stack_expected = f.read()
    with open(f'{file_base}/dmesg') as f:
        crash, stack = helper.get_summaries(f)
    assert crash == crash_expected
    assert stack == stack_expected


@pytest.mark.asyncio
async def test_submit_bad_name():
    assert (await helper.submit('not-a-zip.txt')).code == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_submit_succeed(monkeypatch):
    monkeypatch.setattr(steam, 'get_steam_account_id', lambda: 0)
    response = FakeResponse()
    response.success(monkeypatch)
    assert (await helper.submit(f'{file_base}/dmesg.zip')).code == HelperResult.OK
    assert response.attempt == 3


@pytest.mark.asyncio
async def test_submit_empty(monkeypatch):
    monkeypatch.setattr(crash, 'upload', awaitable(lambda **kwargs: False))
    assert (await helper.submit(f'{file_base}/empty.zip')).code == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_submit_bad_zip(monkeypatch):
    monkeypatch.setattr(crash, 'upload', awaitable(lambda **kwargs: False))
    assert (await helper.submit(f'{file_base}/bad.zip')).code == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_collect_none():
    assert not await helper.collect()
