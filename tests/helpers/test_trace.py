# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import math
import os
import pytest

import steamos_log_submitter as sls
from steamos_log_submitter.helpers.trace import TraceHelper as helper
from steamos_log_submitter.helpers.trace import \
    TraceEvent, TraceLine

from .. import awaitable
from .. import data_directory  # NOQA: F401

file_base = f'{os.path.dirname(__file__)}/trace'


def test_line():
    line = TraceLine(' GamepadUI-Input-4886    [003] .N.1. 23828.572941: mark_victim: pid=14351')
    assert line.task == 'GamepadUI-Input'
    assert line.pid == 4886
    assert line.cpu == 3
    assert math.fabs(line.timestamp - 23828.572941) < 0.000001
    assert line.function == 'mark_victim'
    assert line.extra_args == ['pid=14351']


def test_invalid_line():
    try:
        TraceLine(' GamepadUI Input!4886    [003] .N.1. 23828.572941: mark_victim: pid=14351')
        assert False
    except ValueError:
        pass

    try:
        TraceLine(' GamepadUI Input-48?6    [003] .N.1. 23828.572941: mark_victim: pid=14351')
        assert False
    except ValueError:
        pass

    try:
        TraceLine(' GamepadUI Input-48?6    [003] .N.1. 23828.572941:')
        assert False
    except ValueError:
        pass

    try:
        TraceLine(' GamepadUI Input-48?6    [???] .N.1. 23828.572941: mark_victim: pid=14351')
        assert False
    except ValueError:
        pass


@pytest.mark.asyncio
async def test_oom_event(monkeypatch):
    monkeypatch.setattr(sls.util, 'get_appid', lambda x: 12345 if x == 14351 else None)
    monkeypatch.setattr(helper, 'read_journal', awaitable(lambda *args, **kwargs: None))

    line = ' GamepadUI Input-4886    [003] .N.1. 23828.572941: mark_victim: pid=14351'
    event = await helper.prepare_event(line, {})
    assert event.type == TraceEvent.Type.OOM
    assert event.pid == 14351
    assert event.appid == 12345
    assert math.fabs(event.uptime - 23828.572941) < 0.000001


@pytest.mark.asyncio
async def test_oom_event_invalid(monkeypatch):
    monkeypatch.setattr(sls.util, 'get_appid', lambda x: 12345 if x == 14351 else None)
    monkeypatch.setattr(helper, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))

    line = ' GamepadUI Input-4886    [003] .N.1. 23828.572941: mark_victim:'
    try:
        await helper.prepare_event(line, {})
        assert False
    except ValueError:
        pass

    line = ' GamepadUI Input-4886    [003] .N.1. 23828.572941: mark_victim: pod=14351'
    try:
        await helper.prepare_event(line, {})
        assert False
    except ValueError:
        pass

    line = ' GamepadUI Input-4886    [003] .N.1. 23828.572941: mark_victim: pid=I4351'
    try:
        await helper.prepare_event(line, {})
        assert False
    except ValueError:
        pass


def test_event_dump():
    event = TraceEvent(TraceEvent.Type.OOM)
    event.timestamp = 0.0
    assert json.loads(event.to_json()) == {'type': 'oom'}

    event.pid = 1
    assert json.loads(event.to_json()) == {'type': 'oom', 'pid': 1}

    event.pid = None
    event.appid = 1
    assert json.loads(event.to_json()) == {'type': 'oom', 'appid': 1}

    event.appid = None
    event.timestamp = 1.0
    assert json.loads(event.to_json()) == {'type': 'oom', 'timestamp': 1.0}

    event.timestamp = 0.0
    event.uptime = 1.0
    assert json.loads(event.to_json()) == {'type': 'oom', 'uptime': 1.0}


@pytest.mark.asyncio
async def test_read_journal_split_lock(monkeypatch, data_directory):
    async def read_journal(unit, cursor, current_boot):
        assert unit == 'kernel'
        assert current_boot is True

        f = open(f'{file_base}/split.journal')
        return (json.loads(line) for line in f), None

    monkeypatch.setattr(sls.util, 'read_journal', read_journal)

    logs = await helper.read_journal(TraceEvent.Type.SPLIT_LOCK, 467819546)
    assert logs == ['x86/split lock detection: #AC: CContentUpdateC/50909 took a split_lock trap at address: 0xe4b04c8f']
    assert helper.data['split_lock.cursor'] == 's=4b2d7f42939e4ee1a134a9868400ec66;i=2fc1134;b=39d7eeb17922499aadf23165e93d76fc;m=1be16657;t=610f8f5441b3e;x=85b4e06b52707ed9'


@pytest.mark.asyncio
async def test_read_journal_timing(monkeypatch, data_directory):
    async def read_journal(unit, cursor, current_boot):
        assert unit == 'kernel'
        assert current_boot is True

        f = open(f'{file_base}/split.journal')
        return (json.loads(line) for line in f), None

    monkeypatch.setattr(sls.util, 'read_journal', read_journal)

    logs = await helper.read_journal(TraceEvent.Type.SPLIT_LOCK, 467869090)
    assert logs == ['x86/split lock detection: #AC: CContentUpdateC/50910 took a split_lock trap at address: 0xe4b04c8f']
    assert helper.data['split_lock.cursor'] == 's=4b2d7f42939e4ee1a134a9868400ec66;i=2fc1135;b=39d7eeb17922499aadf23165e93d76fc;m=1be166b2;t=610f8f5441b99;x=9ede380c30ce54a6'
