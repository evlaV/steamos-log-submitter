# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import gzip
import json
import os
import pytest
import subprocess
import time
import steamos_log_submitter as sls
import steamos_log_submitter.helpers.journal as helper
from .. import unreachable, helper_directory, mock_config, patch_module, count_hits
from ..dbus import mock_dbus, MockDBusInterface, MockDBusObject

bus = 'org.freedesktop.systemd1'
iface = 'org.freedesktop.systemd1.Unit'
base = '/org/freedesktop/systemd1/unit'


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


def test_collect_success(monkeypatch, mock_dbus, mock_config, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    assert helper.collect()
    assert count_hits.hits == 1
    assert mock_config.has_section('helpers.journal')
    assert mock_config.has_option('helpers.journal', 'unit_2eservice.cursor')
    assert mock_config.get('helpers.journal', 'unit_2eservice.cursor') == 'cursor'
    with gzip.open(f'{sls.pending}/journal/unit_2eservice.json.gz', 'rt') as f:
        log = json.load(f)
    assert log == ['log']


def test_collect_append(monkeypatch, mock_dbus, mock_config, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    with gzip.open(f'{sls.pending}/journal/unit_2eservice.json.gz', 'wt') as f:
        json.dump(['old'], f)
    assert helper.collect()
    assert count_hits.hits == 1
    assert mock_config.has_section('helpers.journal')
    assert mock_config.has_option('helpers.journal', 'unit_2eservice.cursor')
    assert mock_config.get('helpers.journal', 'unit_2eservice.cursor') == 'cursor'
    with gzip.open(f'{sls.pending}/journal/unit_2eservice.json.gz', 'rt') as f:
        log = json.load(f)
    assert log == ['old', 'log']


def test_collect_corrupted(monkeypatch, mock_dbus, mock_config, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    with open(f'{sls.pending}/journal/unit_2eservice.json.gz', 'w') as f:
        f.write('definitely not json!')
    assert helper.collect()
    assert count_hits.hits == 1
    assert mock_config.has_section('helpers.journal')
    assert mock_config.has_option('helpers.journal', 'unit_2eservice.cursor')
    assert mock_config.get('helpers.journal', 'unit_2eservice.cursor') == 'cursor'
    with gzip.open(f'{sls.pending}/journal/unit_2eservice.json.gz', 'rt') as f:
        log = json.load(f)
    assert log == ['log']


def test_collect_read_error(monkeypatch, mock_dbus, mock_config, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    with gzip.open(f'{sls.pending}/journal/unit_2eservice.json.gz', 'wt') as f:
        json.dump(['old'], f)
    os.chmod(f'{sls.pending}/journal/unit_2eservice.json.gz', 0o200)
    assert os.access(f'{sls.pending}/journal/unit_2eservice.json.gz', os.F_OK)
    if os.access(f'{sls.pending}/journal/unit_2eservice.json.gz', os.R_OK):
        pytest.skip('File is readable, are we running as root?')
    assert not helper.collect()
    assert os.access(f'{sls.pending}/journal/unit_2eservice.json.gz', os.F_OK)
    assert not os.access(f'{sls.pending}/journal/unit_2eservice.json.gz', os.R_OK)


def test_collect_write_error(monkeypatch, mock_dbus, mock_config, count_hits, helper_directory, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', count_hits)
    count_hits.ret = ['log'], 'cursor'
    os.mkdir(f'{sls.pending}/journal')

    with gzip.open(f'{sls.pending}/journal/unit_2eservice.json.gz', 'wt') as f:
        json.dump(['old'], f)
    os.chmod(f'{sls.pending}/journal/unit_2eservice.json.gz', 0o400)
    assert os.access(f'{sls.pending}/journal/unit_2eservice.json.gz', os.F_OK)
    if os.access(f'{sls.pending}/journal/unit_2eservice.json.gz', os.W_OK):
        pytest.skip('File is readable, are we running as root?')
    assert not helper.collect()
    assert os.access(f'{sls.pending}/journal/unit_2eservice.json.gz', os.F_OK)
    assert not os.access(f'{sls.pending}/journal/unit_2eservice.json.gz', os.W_OK)


def test_journal_error(monkeypatch, mock_dbus, mock_unit):
    monkeypatch.setattr(helper, 'read_journal', lambda *args: (None, None))
    monkeypatch.setattr(gzip, 'open', unreachable)

    assert not helper.collect()


def test_journal_cursor_read(monkeypatch, mock_dbus, mock_config, mock_unit):
    configured_cursor = 'Passport'

    def check_cursor(unit, cursor=None):
        assert cursor == configured_cursor
        return None, None

    monkeypatch.setattr(helper, 'read_journal', check_cursor)

    mock_config.add_section('helpers.journal')
    mock_config.set('helpers.journal', 'unit_2eservice.cursor', configured_cursor)

    assert not helper.collect()


def test_journal_cursor_update(monkeypatch, mock_dbus, mock_config, mock_unit, helper_directory):
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

    assert mock_config.has_section('helpers.journal')
    assert mock_config.has_option('helpers.journal', 'unit_2eservice.cursor')
    assert mock_config.get('helpers.journal', 'unit_2eservice.cursor') == 'foo'


def test_journal_invocation_prune(monkeypatch, mock_dbus, mock_config, mock_unit, helper_directory):
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

    with gzip.open(f'{sls.pending}/journal/unit_2eservice.json.gz', 'rt') as f:
        log = json.load(f)
    assert len(log) == 2


def test_journal_invocation_merge(monkeypatch, mock_dbus, mock_config, mock_unit, helper_directory):
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

    with gzip.open(f'{sls.pending}/journal/unit_2eservice.json.gz', 'rt') as f:
        log = json.load(f)
    assert len(log) == 4


def test_submit_bad_name():
    assert not helper.submit('not-a-log.bin')
