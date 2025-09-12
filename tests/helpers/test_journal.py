# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import builtins
import json
import os
import pytest
import steamos_log_submitter as sls
import steamos_log_submitter.aggregators.sentry as sentry
from steamos_log_submitter.helpers import HelperResult
from steamos_log_submitter.helpers.journal import JournalHelper as helper
from .. import always_raise, awaitable, unreachable, Process
from .. import data_directory, count_hits, drop_root, fake_async_subprocess, helper_directory, mock_config, patch_module  # NOQA: F401


@pytest.mark.asyncio
async def test_no_failed(monkeypatch):
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (
        [{
            "JOB_RESULT": "done",
            "INVOCATION_ID": "1234",
            "UNIT": "unit.service",
        }],
        None)
    ))

    assert await helper.failed_units(False, None) == ({}, None)


@pytest.mark.asyncio
async def test_failed(monkeypatch):
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (
        [{
            "JOB_RESULT": "failed",
            "INVOCATION_ID": "1234",
            "UNIT": "unit.service",
        }],
        None)
    ))

    assert await helper.failed_units(False, None) == ({'unit.service': {'1234'}}, None)


@pytest.mark.asyncio
async def test_collect_no_failed(monkeypatch):
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(helper, 'read_journal', unreachable)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (
        [{
            "JOB_RESULT": "done",
            "INVOCATION_ID": "1234",
            "UNIT": "unit.service",
        }],
        None)
    ))

    assert not await helper.collect()


@pytest.mark.asyncio
async def test_collect_success(monkeypatch, data_directory, count_hits, helper_directory):
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(count_hits))
    count_hits.ret = [{
        "JOB_RESULT": "failed",
        "INVOCATION_ID": "1234",
        "UNIT": "unit.service",
    }], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    assert await helper.collect() == ['unit_2eservice 1234.json']
    assert count_hits.hits == 2
    assert os.access(f'{data_directory}/helpers.journal.json', os.F_OK)
    assert 'unit_2eservice.cursor' in helper.data
    assert helper.data.get('unit_2eservice.cursor') == 'cursor'
    with open(f'{sls.pending}/journal/unit_2eservice 1234.json', 'rt') as f:
        log = json.load(f)
    assert log == [{
        "JOB_RESULT": "failed",
        "INVOCATION_ID": "1234",
        "UNIT": "unit.service",
    }]


@pytest.mark.asyncio
async def test_collect_append(monkeypatch, data_directory, count_hits, helper_directory):
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(count_hits))
    count_hits.ret = [{
        "JOB_RESULT": "failed",
        "INVOCATION_ID": "1234",
        "UNIT": "unit.service",
        "MESSAGE": "2",
    }], 'cursor2'
    os.mkdir(f'{sls.pending}/journal')

    with open(f'{sls.pending}/journal/unit_2eservice 1234.json', 'wt') as f:
        json.dump([{'INVOCATION_ID': '1234', 'UNIT': 'unit.service'}], f)
    assert await helper.collect() == ['unit_2eservice 1234.json']
    assert count_hits.hits == 2
    assert os.access(f'{data_directory}/helpers.journal.json', os.F_OK)
    assert 'unit_2eservice.cursor' in helper.data
    assert helper.data.get('unit_2eservice.cursor') == 'cursor2'
    with open(f'{sls.pending}/journal/unit_2eservice 1234.json', 'rt') as f:
        log = json.load(f)
    assert log == [
        {
            "INVOCATION_ID": "1234",
            "UNIT": "unit.service",
        },
        {
            "JOB_RESULT": "failed",
            "INVOCATION_ID": "1234",
            "UNIT": "unit.service",
            "MESSAGE": "2",
        }
    ]


@pytest.mark.asyncio
async def test_collect_corrupted(monkeypatch, data_directory, count_hits, helper_directory):
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(count_hits))
    count_hits.ret = [{
        "JOB_RESULT": "failed",
        "INVOCATION_ID": "1234",
        "UNIT": "unit.service",
        "MESSAGE": "2",
    }], 'cursor2'
    os.mkdir(f'{sls.pending}/journal')

    with open(f'{sls.pending}/journal/unit_2eservice 1234.json', 'wt') as f:
        f.write('definitely not json!')
    assert await helper.collect() == ['unit_2eservice 1234.json']
    assert count_hits.hits == 2
    assert os.access(f'{data_directory}/helpers.journal.json', os.F_OK)
    assert 'unit_2eservice.cursor' in helper.data
    assert helper.data.get('unit_2eservice.cursor') == 'cursor2'
    with open(f'{sls.pending}/journal/unit_2eservice 1234.json', 'rt') as f:
        log = json.load(f)
    assert log == [{
        "JOB_RESULT": "failed",
        "INVOCATION_ID": "1234",
        "UNIT": "unit.service",
        "MESSAGE": "2",
    }]


@pytest.mark.asyncio
async def test_collect_read_error(monkeypatch, data_directory, drop_root, count_hits, helper_directory):
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(count_hits))
    count_hits.ret = [{
        "JOB_RESULT": "failed",
        "INVOCATION_ID": "1234",
        "UNIT": "unit.service",
        "MESSAGE": "2",
    }], 'cursor2'
    os.mkdir(f'{sls.pending}/journal')

    with open(f'{sls.pending}/journal/unit_2eservice 1234.json', 'wt') as f:
        json.dump([{'INVOCATION_ID': '1234', 'UNIT': 'unit.service'}], f)
    os.chmod(f'{sls.pending}/journal/unit_2eservice 1234.json', 0o200)
    assert os.access(f'{sls.pending}/journal/unit_2eservice 1234.json', os.F_OK)
    if os.access(f'{sls.pending}/journal/unit_2eservice 1234.json', os.R_OK):
        pytest.skip('File is readable, are we running as root?')
    assert not await helper.collect()
    assert os.access(f'{sls.pending}/journal/unit_2eservice 1234.json', os.F_OK)
    assert not os.access(f'{sls.pending}/journal/unit_2eservice 1234.json', os.R_OK)


@pytest.mark.asyncio
async def test_collect_write_error(count_hits, data_directory, drop_root, helper_directory, mock_config, monkeypatch):
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(count_hits))
    count_hits.ret = [{
        "JOB_RESULT": "failed",
        "INVOCATION_ID": "1234",
        "UNIT": "unit.service",
        "MESSAGE": "2",
    }], 'cursor2'
    os.mkdir(f'{sls.pending}/journal')

    with open(f'{sls.pending}/journal/unit_2eservice 1234.json', 'wt') as f:
        json.dump([{'INVOCATION_ID': '1234', 'UNIT': 'unit.service'}], f)
    os.chmod(f'{sls.pending}/journal/unit_2eservice 1234.json', 0o400)
    assert os.access(f'{sls.pending}/journal/unit_2eservice 1234.json', os.F_OK)
    if os.access(f'{sls.pending}/journal/unit_2eservice 1234.json', os.W_OK):
        pytest.skip('File is writable, are we running as root?')
    mtime = os.stat(f'{sls.pending}/journal/unit_2eservice 1234.json').st_mtime
    mock_config.add_section('helpers.journal')
    mock_config.set('helpers.journal', 'newest', f'{mtime:.6f}')
    assert not await helper.collect()
    assert os.access(f'{sls.pending}/journal/unit_2eservice 1234.json', os.F_OK)
    assert not os.access(f'{sls.pending}/journal/unit_2eservice 1234.json', os.W_OK)


@pytest.mark.asyncio
async def test_journal_error(monkeypatch):
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))
    monkeypatch.setattr(builtins, 'open', unreachable)

    assert not await helper.collect()


@pytest.mark.asyncio
async def test_journal_error_cursor(monkeypatch, data_directory, helper_directory):
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(helper, 'failed_units', awaitable(lambda *args: ({'unit.service': set()}, None)))
    monkeypatch.setattr(helper, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))

    helper.data['unit_2eservice.cursor'] = 'foo'
    assert not await helper.collect()

    assert 'unit_2eservice.cursor' in helper.data
    assert helper.data.get('unit_2eservice.cursor') == 'foo'


@pytest.mark.asyncio
async def test_journal_cursor_read(monkeypatch, data_directory):
    configured_cursor = 'Passport'

    async def check_cursor(unit, invocations, cursor=None):
        assert cursor == configured_cursor
        return None, None

    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(helper, 'failed_units', awaitable(lambda *args: ({'unit.service': set()}, None)))
    monkeypatch.setattr(helper, 'read_journal', check_cursor)

    helper.data['unit_2eservice.cursor'] = configured_cursor

    assert not await helper.collect()


@pytest.mark.asyncio
async def test_journal_cursor_update(fake_async_subprocess, data_directory, helper_directory, monkeypatch):
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(helper, 'failed_units', awaitable(lambda *args: ({'unit.service': {'1234'}}, None)))
    lines = [json.dumps({
        '__CURSOR': str(x),
        '_SYSTEMD_UNIT': 'unit.service',
        'INVOCATION_ID': '1234'
    }) for x in range(20)]
    lines.append(json.dumps({
        '__CURSOR': 'foo',
        '_SYSTEMD_UNIT': 'unit.service',
        'UNIT_RESULT': 'bar',
        'INVOCATION_ID': '1234'
    }))
    lines.append('')
    fake_async_subprocess(stdout='\n'.join(lines).encode())
    os.mkdir(f'{sls.pending}/journal')

    assert await helper.collect()

    assert os.access(f'{data_directory}/helpers.journal.json', os.F_OK)
    assert 'unit_2eservice.cursor' in helper.data
    assert helper.data.get('unit_2eservice.cursor') == 'foo'


@pytest.mark.asyncio
async def test_journal_invocation_prune(fake_async_subprocess, data_directory, helper_directory, monkeypatch):
    monkeypatch.setattr(helper, 'units', ['unit.service'])

    lines = []
    for x in range(5):
        line = {
            '__CURSOR': str(x * 2),
            'UNIT': 'unit.service',
            '_SYSTEMD_UNIT': 'init.scope',
            'INVOCATION_ID': str(x),
        }
        if x & 1:
            line['JOB_RESULT'] = 'failed'
        lines.append(json.dumps(line))
        line = {
            '__CURSOR': str(x * 2 + 1),
            '_SYSTEMD_UNIT': 'unit.service',
            'INVOCATION_ID': str(x),
        }
        lines.append(json.dumps(line))
    lines.append('')
    fake_async_subprocess(stdout='\n'.join(lines).encode())
    os.mkdir(f'{sls.pending}/journal')

    assert len(await helper.collect()) == 2

    assert not os.access(f'{sls.pending}/journal/unit_2eservice 0.json', os.F_OK)
    assert os.access(f'{sls.pending}/journal/unit_2eservice 1.json', os.F_OK)
    assert not os.access(f'{sls.pending}/journal/unit_2eservice 2.json', os.F_OK)
    assert os.access(f'{sls.pending}/journal/unit_2eservice 3.json', os.F_OK)
    assert not os.access(f'{sls.pending}/journal/unit_2eservice 4.json', os.F_OK)


@pytest.mark.asyncio
async def test_journal_invocation_merge(monkeypatch, data_directory, helper_directory):
    monkeypatch.setattr(helper, 'units', ['unit.service'])

    async def fake_subprocess(*args, **kwargs):
        lines = []
        for x in range(5):
            line = {
                '__CURSOR': str(x * 2),
                '_SYSTEMD_UNIT': 'init.scope',
                'INVOCATION_ID': str(x // 2),
                'UNIT': 'unit.service',
            }
            if x & 1:
                line['JOB_RESULT'] = 'failed'
            lines.append(json.dumps(line))
            line = {
                '__CURSOR': str(x * 2 + 1),
                '_SYSTEMD_UNIT': 'unit.service',
                'INVOCATION_ID': str(x // 2),
            }
            lines.append(json.dumps(line))
        lines.append('')
        ret = Process(stdout='\n'.join(lines).encode())
        return ret

    os.mkdir(f'{sls.pending}/journal')
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', fake_subprocess)

    assert await helper.collect()

    with open(f'{sls.pending}/journal/unit_2eservice 0.json', 'rt') as f:
        log = json.load(f)
    assert len(log) == 2

    with open(f'{sls.pending}/journal/unit_2eservice 1.json', 'rt') as f:
        log = json.load(f)
    assert len(log) == 2

    assert not os.access(f'{sls.pending}/journal/unit_2eservice 2.json', os.F_OK)


def test_escape():
    assert helper.escape('abc/def_') == 'abc_2fdef_5f'


def test_unescape():
    assert helper.unescape('abc_2fdef_5f') == 'abc/def_'
    assert helper.unescape('abc_2xdef_5f') == 'abcdef_'
    assert helper.unescape('abc_xdef_5f') == 'abcef_'


@pytest.mark.asyncio
async def test_submit_params(helper_directory, mock_config, monkeypatch):
    async def fake_submit(self):
        assert len(self.attachments) == 1
        assert self.attachments[0]['mime-type'] == 'application/json'
        assert self.attachments[0]['filename'] == 'abc_5fdef.json'
        assert self.attachments[0]['data'] == b'[{"MESSAGE":"Whoa"}]'
        assert self.tags['unit'] == 'abc_def'
        assert self.message == 'abc_def\nWhoa'
        assert 'unit:abc_def' in self.fingerprint
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', fake_submit)
    mock_config.add_section('helpers.journal')
    mock_config.set('helpers.journal', 'dsn', 'https://fake@dsn')

    with open(f'{helper_directory}/abc_5fdef.json', 'w') as f:
        f.write('[{"MESSAGE":"Whoa"}]')
    assert await helper.submit(f'{helper_directory}/abc_5fdef.json') == HelperResult.OK


@pytest.mark.asyncio
async def test_subprocess_failure(monkeypatch, data_directory, helper_directory):
    os.mkdir(f'{sls.pending}/journal')
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', always_raise(OSError))

    assert not await helper.collect()
