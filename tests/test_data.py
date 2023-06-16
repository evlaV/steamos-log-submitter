# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import os
import pytest
import steamos_log_submitter.data as data
from . import data_directory  # NOQA: F401


@pytest.fixture(autouse=True)
def clear_data(data_directory, monkeypatch):
    monkeypatch.setattr(data, 'datastore', {})


def test_no_data(data_directory):
    assert os.access(data_directory, os.F_OK)
    assert not os.access(f'{data_directory}/test.json', os.F_OK)
    d = data.get_data('test')
    assert d
    assert not d._data
    assert not os.access(f'{data_directory}/test.json', os.F_OK)


def test_have_data(data_directory):
    assert os.access(data_directory, os.F_OK)
    assert not os.access(f'{data_directory}/test.json', os.F_OK)
    with open(f'{data_directory}/test.json', 'w') as f:
        json.dump({'foo': 1}, f)
    d = data.get_data('test')
    assert d
    assert d['foo'] == 1


def test_default(data_directory):
    d = data.get_data('test', defaults={'foo': 1})
    assert d
    assert not d._data
    assert d['foo'] == 1


def test_missing_key(data_directory):
    d = data.get_data('test')
    assert d
    assert not d._data
    try:
        d['foo']
        assert False
    except KeyError:
        pass


def test_set_key(data_directory):
    d = data.get_data('test')
    assert d
    assert not d._data
    d['foo'] = 1
    assert d['foo'] == 1


def test_shared_data(data_directory):
    d1 = data.get_data('test')
    d2 = data.get_data('test')
    assert d1
    assert d2
    try:
        d2['foo']
        assert False
    except KeyError:
        pass
    d1['foo'] = 1
    assert d2['foo'] == 1


def test_new_defaults(data_directory):
    d = data.get_data('test')
    assert d
    try:
        d['foo']
        assert False
    except KeyError:
        pass
    d.add_defaults({'foo': 1})
    assert d['foo'] == 1


def test_new_defaults2(data_directory):
    d = data.get_data('test')
    assert d
    try:
        d['foo']
        assert False
    except KeyError:
        pass
    d = data.get_data('test', {'foo': 1})
    assert d
    assert d['foo'] == 1


def test_get(data_directory):
    d = data.get_data('test')
    assert d
    try:
        d['foo']
        assert False
    except KeyError:
        pass
    assert d.get('foo') is None
    assert d.get('foo', 1) == 1


def test_write(data_directory):
    assert os.access(data_directory, os.F_OK)
    assert not os.access(f'{data_directory}/test.json', os.F_OK)
    d = data.get_data('test')
    assert d
    assert not d._data
    d['foo'] = 1
    d.write()
    assert os.access(f'{data_directory}/test.json', os.F_OK)
    with open(f'{data_directory}/test.json') as f:
        assert json.load(f) == {"foo": 1}


def test_write_all(data_directory):
    assert os.access(data_directory, os.F_OK)
    assert not os.access(f'{data_directory}/test.json', os.F_OK)
    d = data.get_data('test')
    assert d
    assert not d._data
    d['foo'] = 1
    data.write_all()
    assert os.access(f'{data_directory}/test.json', os.F_OK)
    with open(f'{data_directory}/test.json') as f:
        assert json.load(f) == {"foo": 1}
