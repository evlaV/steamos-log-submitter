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

from . import open_shim  # NOQA: F401
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
        monkeypatch.setattr(buffer, 'fileno', lambda: -1)
        return buffer

    d = tempfile.TemporaryDirectory(prefix='sls-')
    monkeypatch.setattr(sls, 'base', d.name)
    monkeypatch.setattr(builtins, 'open', fake_open)
    monkeypatch.setattr(os, 'makedirs', lambda *args: None)
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
