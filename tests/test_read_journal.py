# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import json
import pytest
import steamos_log_submitter as sls
from . import always_raise
from . import fake_async_subprocess  # NOQA: F401
from .dbus import mock_dbus  # NOQA: F401


@pytest.mark.asyncio
async def test_journal_cursor_update(fake_async_subprocess, mock_dbus):
    lines = [json.dumps({'__CURSOR': str(x)}) for x in range(20)]
    lines.append(json.dumps({'__CURSOR': 'foo'}))
    lines.append('')
    fake_async_subprocess(stdout='\n'.join(lines).encode())

    logs, cursor = await sls.util.read_journal('unit')
    assert cursor == 'foo'


@pytest.mark.asyncio
async def test_subprocess_failure(monkeypatch, mock_dbus):
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', always_raise(OSError))

    assert await sls.util.read_journal('steamos_log_submitter.service') == (None, None)
