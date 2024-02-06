# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import builtins
import io
import os
import pytest
import shutil
import tempfile

import steamos_log_submitter as sls
import steamos_log_submitter.ftraced as ftraced

from . import always_raise
from . import count_hits, open_shim  # NOQA: F401
from .dbus import mock_dbus  # NOQA: F401


@pytest.mark.asyncio
async def test_unmached_close():
    daemon = ftraced.FtraceDaemon()
    await daemon.close()


@pytest.mark.asyncio
async def test_open(mock_dbus, monkeypatch):
    buffers: dict[str, io.StringIO | io.BytesIO] = {}

    def fake_open(fname: str, mode: str = 'r') -> io.IOBase:
        buffer: io.StringIO | io.BytesIO
        if 'b' in mode:
            buffer = io.BytesIO()
        else:
            buffer = io.StringIO()
        buffers[fname] = buffer
        monkeypatch.setattr(buffer, 'close', lambda: None)
        return buffer

    d = tempfile.TemporaryDirectory(prefix='sls-')
    monkeypatch.setattr(sls, 'base', d.name)
    monkeypatch.setattr(builtins, 'open', fake_open)
    monkeypatch.setattr(os, 'makedirs', lambda *args, **kwargs: None)
    loop = asyncio.get_event_loop()
    monkeypatch.setattr(loop, 'add_reader', lambda *args, **kwargs: None)
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    daemon = ftraced.FtraceDaemon()
    await daemon.open()

    assert len(buffers) == 4
    assert buffers[f'{daemon.BASE}/events/oom/mark_victim/enable'].getvalue() == '1'
    assert buffers[f'{daemon.BASE}/set_ftrace_filter'].getvalue() == 'split_lock_warn'
    assert buffers[f'{daemon.BASE}/current_tracer'].getvalue() == 'function'
    assert f'{daemon.BASE}/trace_pipe' in buffers


@pytest.mark.asyncio
async def test_socket_shutdown(mock_dbus, monkeypatch, open_shim):
    d = tempfile.TemporaryDirectory(prefix='sls-')
    monkeypatch.setattr(sls, 'base', d.name)
    monkeypatch.setattr(ftraced.FtraceDaemon, 'BASE', f'{d.name}/trace')
    loop = asyncio.get_event_loop()
    monkeypatch.setattr(loop, 'add_reader', lambda *args, **kwargs: None)
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    open_shim.empty()
    daemon = ftraced.FtraceDaemon()
    await daemon.open()
    assert daemon.pipe is not None
    assert daemon.server is not None

    _, writer = await asyncio.open_unix_connection(f'{sls.base}/ftraced.sock')
    writer.write(b'shutdown\n')
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    await asyncio.sleep(0.01)
    assert daemon.server.is_serving() is False


@pytest.mark.asyncio
async def test_run(mock_dbus, monkeypatch, open_shim):
    d = tempfile.TemporaryDirectory(prefix='sls-')
    monkeypatch.setattr(sls, 'base', d.name)
    monkeypatch.setattr(ftraced.FtraceDaemon, 'BASE', f'{d.name}/trace')
    loop = asyncio.get_event_loop()
    monkeypatch.setattr(loop, 'add_reader', lambda *args, **kwargs: None)
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    open_shim.empty()
    daemon = ftraced.FtraceDaemon()
    task = asyncio.create_task(daemon.run())
    assert daemon.pipe is None
    assert daemon.server is None

    await asyncio.sleep(0.01)
    assert daemon.pipe is not None
    assert daemon.server is not None

    _, writer = await asyncio.open_unix_connection(f'{sls.base}/ftraced.sock')
    writer.write(b'shutdown\n')
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    await asyncio.wait([task])
    assert daemon.server is None


@pytest.mark.asyncio
async def test_pipe_event(count_hits, monkeypatch):
    async def _send_event(line: str, data):
        assert line == ' GamepadUI Input-4886    [003] .N.1. 23828.572941: mark_victim: pid=14351'
        assert data == {'appid': 12345, 'comm': 'GamepadUI!'}
        count_hits()

    monkeypatch.setattr(sls.util, 'get_appid', lambda _: 12345)
    monkeypatch.setattr(sls.util, 'get_pid_stat', lambda _: ('GamepadUI!', None))
    monkeypatch.setattr(os, 'readlink', always_raise(PermissionError))

    d = tempfile.TemporaryDirectory(prefix='sls-')
    trace_pipe = open(f'{d.name}/trace_pipe', 'wb', buffering=False)
    trace_pipe.write(b' GamepadUI Input-4886    [003] .N.1. 23828.572941: mark_victim: pid=14351\n')

    daemon = ftraced.FtraceDaemon()
    monkeypatch.setattr(daemon, '_send_event', _send_event)
    daemon.pipe = open(f'{d.name}/trace_pipe', 'rb')

    assert len(daemon._tasks) == 0
    daemon._pipe_event()
    assert len(daemon._tasks) == 1
    await asyncio.wait(daemon._tasks)
    assert count_hits.hits == 1
