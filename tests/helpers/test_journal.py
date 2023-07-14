# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import json
import os
import pytest
import subprocess
import steamos_log_submitter as sls
import steamos_log_submitter.sentry as sentry
from steamos_log_submitter.helpers import create_helper, HelperResult
from .. import always_raise, unreachable
from .. import data_directory, count_hits, drop_root, helper_directory, mock_config, patch_module  # NOQA: F401
from ..dbus import mock_dbus, MockDBusObject  # NOQA: F401

bus = 'org.freedesktop.systemd1'
iface = 'org.freedesktop.systemd1.Unit'
base = '/org/freedesktop/systemd1/unit'

helper = create_helper('journal')


@pytest.fixture
def mock_unit(monkeypatch, mock_dbus):
    mock_dbus.add_bus(bus)
    service = MockDBusObject(bus, f'{base}/unit_2eservice', mock_dbus)
    service.properties[iface] = {
        'ActiveState': 'failed'
    }
    monkeypatch.setattr(helper, 'units', ['unit.service'])


def test_collect_no_failed(monkeypatch, mock_dbus):
    mock_dbus.add_bus(bus)
    service = MockDBusObject(bus, f'{base}/unit_2eservice', mock_dbus)
    service.properties[iface] = {
        'ActiveState': 'inactive'
    }
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(helper, 'read_journal', unreachable)

    assert not helper.collect()


def test_collect_dbus_exception(monkeypatch, mock_dbus):
    mock_dbus.add_bus(bus)
    monkeypatch.setattr(helper, 'units', ['unit.service'])
    monkeypatch.setattr(helper, 'read_journal', unreachable)

    assert not helper.collect()


def test_collect_success(monkeypatch, mock_dbus, data_directory, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    assert helper.collect()
    assert count_hits.hits == 1
    assert os.access(f'{data_directory}/helpers.journal.json', os.F_OK)
    assert 'unit_2eservice.cursor' in helper.data
    assert helper.data.get('unit_2eservice.cursor') == 'cursor'
    with open(f'{sls.pending}/journal/unit_2eservice.json', 'rt') as f:
        log = json.load(f)
    assert log == ['log']


def test_collect_append(monkeypatch, mock_dbus, data_directory, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    with open(f'{sls.pending}/journal/unit_2eservice.json', 'wt') as f:
        json.dump(['old'], f)
    assert helper.collect()
    assert count_hits.hits == 1
    assert os.access(f'{data_directory}/helpers.journal.json', os.F_OK)
    assert 'unit_2eservice.cursor' in helper.data
    assert helper.data.get('unit_2eservice.cursor') == 'cursor'
    with open(f'{sls.pending}/journal/unit_2eservice.json', 'rt') as f:
        log = json.load(f)
    assert log == ['old', 'log']


def test_collect_corrupted(monkeypatch, mock_dbus, data_directory, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    with open(f'{sls.pending}/journal/unit_2eservice.json', 'w') as f:
        f.write('definitely not json!')
    assert helper.collect()
    assert count_hits.hits == 1
    assert os.access(f'{data_directory}/helpers.journal.json', os.F_OK)
    assert 'unit_2eservice.cursor' in helper.data
    assert helper.data.get('unit_2eservice.cursor') == 'cursor'
    with open(f'{sls.pending}/journal/unit_2eservice.json', 'rt') as f:
        log = json.load(f)
    assert log == ['log']


def test_collect_read_error(monkeypatch, mock_dbus, data_directory, drop_root, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    with open(f'{sls.pending}/journal/unit_2eservice.json', 'wt') as f:
        json.dump(['old'], f)
    os.chmod(f'{sls.pending}/journal/unit_2eservice.json', 0o200)
    assert os.access(f'{sls.pending}/journal/unit_2eservice.json', os.F_OK)
    if os.access(f'{sls.pending}/journal/unit_2eservice.json', os.R_OK):
        pytest.skip('File is readable, are we running as root?')
    assert not helper.collect()
    assert os.access(f'{sls.pending}/journal/unit_2eservice.json', os.F_OK)
    assert not os.access(f'{sls.pending}/journal/unit_2eservice.json', os.R_OK)


def test_collect_write_error(monkeypatch, mock_dbus, data_directory, drop_root, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    with open(f'{sls.pending}/journal/unit_2eservice.json', 'wt') as f:
        json.dump(['old'], f)
    os.chmod(f'{sls.pending}/journal/unit_2eservice.json', 0o400)
    assert os.access(f'{sls.pending}/journal/unit_2eservice.json', os.F_OK)
    if os.access(f'{sls.pending}/journal/unit_2eservice.json', os.W_OK):
        pytest.skip('File is readable, are we running as root?')
    assert not helper.collect()
    assert os.access(f'{sls.pending}/journal/unit_2eservice.json', os.F_OK)
    assert not os.access(f'{sls.pending}/journal/unit_2eservice.json', os.W_OK)


def test_collect_no_local(monkeypatch, mock_dbus, data_directory, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    monkeypatch.setattr(sls.config, 'write_config', always_raise(FileNotFoundError))
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    assert helper.collect()
    assert count_hits.hits == 1
    assert os.access(f'{data_directory}/helpers.journal.json', os.F_OK)
    assert 'unit_2eservice.cursor' in helper.data
    assert helper.data.get('unit_2eservice.cursor') == 'cursor'
    with open(f'{sls.pending}/journal/unit_2eservice.json', 'rt') as f:
        log = json.load(f)
    assert log == ['log']


def test_journal_error(monkeypatch, mock_dbus, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', lambda *args: (None, None))
    monkeypatch.setattr(builtins, 'open', unreachable)

    assert not helper.collect()


def test_journal_cursor_read(monkeypatch, mock_dbus, data_directory, mock_unit):
    configured_cursor = 'Passport'

    def check_cursor(unit, cursor=None):
        assert cursor == configured_cursor
        return None, None

    monkeypatch.setattr(helper, 'read_journal', check_cursor)

    helper.data['unit_2eservice.cursor'] = configured_cursor

    assert not helper.collect()


def test_journal_cursor_update(monkeypatch, mock_dbus, data_directory, mock_unit, helper_directory):
    def fake_subprocess(*args, **kwargs):
        ret = subprocess.CompletedProcess(args[0], 0)
        lines = [json.dumps({'__CURSOR': str(x)}) for x in range(20)]
        lines.append(json.dumps({'__CURSOR': 'foo', 'UNIT_RESULT': 'bar'}))
        lines.append('')
        ret.stdout = '\n'.join(lines).encode()
        return ret

    os.mkdir(f'{sls.pending}/journal')
    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    assert helper.collect()

    assert os.access(f'{data_directory}/helpers.journal.json', os.F_OK)
    assert 'unit_2eservice.cursor' in helper.data
    assert helper.data.get('unit_2eservice.cursor') == 'foo'


def test_journal_invocation_prune(monkeypatch, mock_dbus, data_directory, mock_unit, helper_directory):
    def fake_subprocess(*args, **kwargs):
        ret = subprocess.CompletedProcess(args[0], 0)
        lines = []
        for x in range(5):
            line = {
                '__CURSOR': str(x),
                'INVOCATION_ID': str(x)
            }
            if x & 1:
                line['UNIT_RESULT'] = 'foo'
            lines.append(json.dumps(line))
        lines.append('')
        ret.stdout = '\n'.join(lines).encode()
        return ret

    os.mkdir(f'{sls.pending}/journal')
    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    assert helper.collect()

    with open(f'{sls.pending}/journal/unit_2eservice.json', 'rt') as f:
        log = json.load(f)
    assert len(log) == 2


def test_journal_invocation_merge(monkeypatch, mock_dbus, data_directory, mock_unit, helper_directory):
    def fake_subprocess(*args, **kwargs):
        ret = subprocess.CompletedProcess(args[0], 0)
        lines = []
        for x in range(5):
            line = {
                '__CURSOR': str(x),
                'INVOCATION_ID': str(x // 2)
            }
            if x & 1:
                line['UNIT_RESULT'] = 'foo'
            lines.append(json.dumps(line))
        lines.append('')
        ret.stdout = '\n'.join(lines).encode()
        return ret

    os.mkdir(f'{sls.pending}/journal')
    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    assert helper.collect()

    with open(f'{sls.pending}/journal/unit_2eservice.json', 'rt') as f:
        log = json.load(f)
    assert len(log) == 4


def test_escape():
    assert helper.escape('abc/def_') == 'abc_2fdef_5f'


def test_unescape():
    assert helper.unescape('abc_2fdef_5f') == 'abc/def_'
    assert helper.unescape('abc_2xdef_5f') == 'abcdef_'
    assert helper.unescape('abc_xdef_5f') == 'abcef_'


def test_submit_bad_name():
    assert helper.submit('not-a-log.bin').code == HelperResult.PERMANENT_ERROR


def test_submit_params(helper_directory, mock_config, monkeypatch):
    def fake_submit(dsn, *, attachments, tags, fingerprint, message):
        assert len(attachments) == 1
        assert attachments[0]['mime-type'] == 'application/json'
        assert attachments[0]['filename'] == 'abc_5fdef.json'
        assert attachments[0]['data'] == b'{}'
        assert tags['unit'] == 'abc_def'
        assert message == 'abc_def'
        assert 'unit:abc_def' in fingerprint
        return HelperResult()

    monkeypatch.setattr(sentry, 'send_event', fake_submit)
    mock_config.add_section('helpers.journal')
    mock_config.set('helpers.journal', 'dsn', 'https://fake@dsn')

    with open(f'{helper_directory}/abc_5fdef.json', 'w') as f:
        f.write('{}')
    assert helper.submit(f'{helper_directory}/abc_5fdef.json').code == HelperResult.OK


def test_subprocess_failure(monkeypatch, mock_dbus, data_directory, mock_unit, helper_directory):
    os.mkdir(f'{sls.pending}/journal')
    monkeypatch.setattr(subprocess, 'run', always_raise(subprocess.SubprocessError()))

    assert not helper.collect()
