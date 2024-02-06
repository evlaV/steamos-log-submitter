# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import math
import steamos_log_submitter as sls
from steamos_log_submitter.helpers.trace import \
    TraceEvent, TraceHelper, TraceLine


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


def test_oom_event(monkeypatch):
    monkeypatch.setattr(sls.util, 'get_appid', lambda x: 12345 if x == 14351 else None)

    line = ' GamepadUI Input-4886    [003] .N.1. 23828.572941: mark_victim: pid=14351'
    event = TraceHelper.prepare_event(line, {})
    assert event.type == TraceEvent.Type.OOM
    assert event.pid == 14351
    assert event.appid == 12345
    assert math.fabs(event.uptime - 23828.572941) < 0.000001


def test_oom_event_invalid(monkeypatch):
    monkeypatch.setattr(sls.util, 'get_appid', lambda x: 12345 if x == 14351 else None)

    line = ' GamepadUI Input-4886    [003] .N.1. 23828.572941: mark_victim:'
    try:
        TraceHelper.prepare_event(line, {})
        assert False
    except ValueError:
        pass

    line = ' GamepadUI Input-4886    [003] .N.1. 23828.572941: mark_victim: pod=14351'
    try:
        TraceHelper.prepare_event(line, {})
        assert False
    except ValueError:
        pass

    line = ' GamepadUI Input-4886    [003] .N.1. 23828.572941: mark_victim: pid=I4351'
    try:
        TraceHelper.prepare_event(line, {})
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
