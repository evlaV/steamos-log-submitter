# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import os
import pytest

import steamos_log_submitter.sentry as sentry
from steamos_log_submitter.helpers import HelperResult
from steamos_log_submitter.helpers.kdump import KdumpHelper as helper
from .. import custom_dsn, unreachable
from .. import fake_pwuid, mock_config  # NOQA: F401

file_base = f'{os.path.dirname(__file__)}/kdump'
dsn = custom_dsn('helpers.kdump')


def test_call_trace_parse():
    with open(f'{file_base}/stack.json') as f:
        stack_expected = json.load(f)
    with open(f'{file_base}/stack') as f:
        stack = f.read().rstrip().split('\n')
    assert stack_expected == helper.parse_traces(stack)


def test_dmesg_parse():
    with open(f'{file_base}/crash') as f:
        crash_expected = f.read()
    with open(f'{file_base}/stack') as f:
        stack_expected = f.read().rstrip().split('\n')
    with open(f'{file_base}/dmesg') as f:
        crash, stack = helper.get_summaries(f)
    assert crash == crash_expected
    assert stack == helper.parse_traces(stack_expected)


def test_dmesg_parse2():
    with open(f'{file_base}/crash2') as f:
        crash_expected = f.read()
    with open(f'{file_base}/stack2') as f:
        stack_expected = f.read().rstrip().split('\n')
    with open(f'{file_base}/dmesg2') as f:
        crash, stack = helper.get_summaries(f)
    print(json.dumps(stack, indent=2))
    print(json.dumps(helper.parse_traces(stack_expected), indent=2))
    assert crash == crash_expected
    assert stack == helper.parse_traces(stack_expected)


@pytest.mark.asyncio
async def test_submit_empty(monkeypatch):
    monkeypatch.setattr(sentry.SentryEvent, 'send', unreachable)
    assert (await helper.submit(f'{file_base}/empty.zip')).code == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_submit_bad_zip(monkeypatch):
    monkeypatch.setattr(sentry.SentryEvent, 'send', unreachable)
    assert (await helper.submit(f'{file_base}/bad.zip')).code == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_submit_multiple_zip(monkeypatch):
    async def check_now(self) -> bool:
        assert len(self.attachments) == 3
        with open(f'{file_base}/stack.json') as f:
            assert self.exceptions == [{'stacktrace': frames, 'type': 'PANIC'} for frames in json.load(f)]
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    assert (await helper.submit(f'{file_base}/dmesg-202310050102.zip')).code == HelperResult.OK


@pytest.mark.asyncio
async def test_submit_multiple_timestamp(monkeypatch):
    async def check_now(self) -> bool:
        assert self.timestamp == 1696467720
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    assert (await helper.submit(f'{file_base}/dmesg-202310050102.zip')).code == HelperResult.OK


@pytest.mark.asyncio
async def test_submit_build_info(monkeypatch):
    async def check_now(self) -> bool:
        assert self.build_id == '20230927.1000'
        assert self.tags['kernel'] == '6.1.52-valve2-1-neptune-61'
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    assert (await helper.submit(f'{file_base}/kdumpst-202310050540.zip')).code == HelperResult.OK


@pytest.mark.asyncio
async def test_collect_none():
    assert not await helper.collect()
