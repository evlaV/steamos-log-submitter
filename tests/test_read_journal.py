# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import json
import pytest
import steamos_log_submitter as sls
from . import always_raise, Process
from . import count_hits, fake_async_subprocess  # NOQA: F401
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
async def test_journal_kernel(count_hits, fake_async_subprocess, monkeypatch):
    tested_unit = ''

    async def test_args(*args, **kwargs):
        count_hits()
        if tested_unit == 'kernel':
            assert list(args) == ['journalctl', '-o', 'json', '-k']
        else:
            assert list(args) == ['journalctl', '-o', 'json', '-u', tested_unit]
        return Process(stdout=b'')

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', test_args)

    tested_unit = 'kernel'
    await sls.util.read_journal(tested_unit)
    assert count_hits.hits == 1

    tested_unit = 'steamos_log_submitter.service'
    await sls.util.read_journal(tested_unit)
    assert count_hits.hits == 2


@pytest.mark.asyncio
async def test_subprocess_failure(monkeypatch, mock_dbus):
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', always_raise(OSError))

    assert await sls.util.read_journal('steamos_log_submitter.service') == (None, None)
