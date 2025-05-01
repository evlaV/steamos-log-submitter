# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import importlib
import os
import pytest
import shutil
import time
import typing

import steamos_log_submitter as sls
import steamos_log_submitter.helpers as helpers

from . import count_hits, helper_directory, mock_config, patch_module, setup_categories  # NOQA: F401
from .daemon import dbus_daemon


def test_staging_file_rename(helper_directory, monkeypatch):
    setup_categories(['test'])
    monkeypatch.setattr(os, 'geteuid', lambda: 998)
    f = helpers.StagingFile('test', 'foo')
    assert not os.access(f'{sls.pending}/test/foo', os.F_OK)
    assert os.access(f.name, os.F_OK)
    ino = os.stat(f.name).st_ino
    f.close()
    assert os.access(f'{sls.pending}/test/foo', os.F_OK)
    assert not os.access(f.name, os.F_OK)
    assert os.stat(f'{sls.pending}/test/foo').st_ino == ino


def test_staging_file_chown(count_hits, helper_directory, monkeypatch):
    def chown(fname, user, *args, **kwargs):
        assert user == 'steamos-log-submitter'
        count_hits()

    setup_categories(['test'])
    monkeypatch.setattr(shutil, 'chown', chown)

    monkeypatch.setattr(os, 'geteuid', lambda: 998)

    f = helpers.StagingFile('test', 'foo')
    f.close()
    assert count_hits.hits == 0

    monkeypatch.setattr(os, 'geteuid', lambda: 0)

    f = helpers.StagingFile('test', 'bar')
    f.close()
    assert count_hits.hits == 1


def test_staging_file_context_manager(helper_directory, monkeypatch):
    setup_categories(['test'])
    monkeypatch.setattr(os, 'geteuid', lambda: 998)
    with helpers.StagingFile('test', 'foo') as f:
        assert not os.access(f'{sls.pending}/test/foo', os.F_OK)
        assert os.access(f.name, os.F_OK)
        ino = os.stat(f.name).st_ino
    assert os.access(f'{sls.pending}/test/foo', os.F_OK)
    assert os.stat(f'{sls.pending}/test/foo').st_ino == ino


def test_list_filtering(patch_module):
    assert patch_module.filter_log('.abc') is False
    assert not patch_module.valid_extensions
    assert patch_module.filter_log('xyz.abc') is True
    patch_module.valid_extensions = {'.json'}
    assert patch_module.filter_log('xyz.abc') is False
    assert patch_module.filter_log('xyz.json') is True


def test_invalid_helper_module(patch_module):
    assert helpers.create_helper('test') is not None
    assert helpers.create_helper('foo') is None


def test_invalid_broken_module(monkeypatch):
    original_import_module = importlib.import_module

    def import_module(name, package=None):
        if name.startswith('steamos_log_submitter.helpers.test'):
            return ()
        return original_import_module(name, package)
    monkeypatch.setattr(importlib, 'import_module', import_module)
    monkeypatch.setattr(helpers, 'list_helpers', lambda: ['test'])

    assert helpers.create_helper('test') is None


@pytest.mark.asyncio
async def test_collect_new_logs(helper_directory, mock_config, patch_module):
    patch_module.valid_extensions = {'.bin'}
    os.mkdir(f'{sls.pending}/test')
    assert not await patch_module.collect()

    with open(f'{sls.pending}/test/a.bin', 'w'):
        pass
    assert await patch_module.collect() == ['a.bin']
    assert not await patch_module.collect()

    time.sleep(0.005)
    with open(f'{sls.pending}/test/b.bin', 'w'):
        pass
    assert await patch_module.collect() == ['b.bin']

    time.sleep(0.005)
    with open(f'{sls.pending}/test/c.bin', 'w'):
        pass
    with open(f'{sls.pending}/test/d.bin', 'w'):
        pass
    assert list(sorted(await patch_module.collect())) == ['c.bin', 'd.bin']
    assert not await patch_module.collect()


@pytest.mark.asyncio
async def test_subscribe_new_logs(count_hits, helper_directory, mock_config, monkeypatch, patch_module):
    patch_module.valid_extensions = {'.bin'}
    os.mkdir(f'{sls.pending}/test')
    collected: list[str] = []
    collected_prefixed: list[str] = []

    def cb(new_logs: list[str]) -> None:
        nonlocal collected
        collected = new_logs
        count_hits()

    def cb_prefixed(new_logs: list[str]) -> None:
        nonlocal collected_prefixed
        collected_prefixed = new_logs
        count_hits()

    daemon, bus = await dbus_daemon(monkeypatch)
    helper = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Test')
    await helper.subscribe(f'{sls.constants.DBUS_NAME}.Helper', 'NewLogs', cb)
    manager = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/Manager')
    await manager.subscribe(f'{sls.constants.DBUS_NAME}.Manager', 'NewLogs', cb_prefixed)

    await patch_module.collect()
    await asyncio.sleep(0.001)

    assert not collected
    assert count_hits.hits == 0

    with open(f'{sls.pending}/test/a.bin', 'w'):
        pass
    await patch_module.collect()
    await asyncio.sleep(0.001)
    assert collected == ['a.bin']
    assert collected_prefixed == ['test/a.bin']
    assert count_hits.hits == 2

    await patch_module.collect()
    await asyncio.sleep(0.001)
    assert count_hits.hits == 2

    await asyncio.sleep(0.005)
    with open(f'{sls.pending}/test/b.bin', 'w'):
        pass
    await patch_module.collect()
    await asyncio.sleep(0.001)
    assert collected == ['b.bin']
    assert collected_prefixed == ['test/b.bin']
    assert count_hits.hits == 4

    await asyncio.sleep(0.005)
    with open(f'{sls.pending}/test/c.bin', 'w'):
        pass
    with open(f'{sls.pending}/test/d.bin', 'w'):
        pass
    await patch_module.collect()
    await asyncio.sleep(0.001)
    assert set(collected) == {'c.bin', 'd.bin'}
    assert set(collected_prefixed) == {'test/c.bin', 'test/d.bin'}
    assert count_hits.hits == 6

    await asyncio.sleep(0.005)
    await patch_module.collect()
    await asyncio.sleep(0.001)
    assert count_hits.hits == 6

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_last_collected_timestamp(helper_directory, mock_config, monkeypatch, patch_module):
    patch_module.valid_extensions = {'.bin'}
    os.mkdir(f'{sls.pending}/test')

    daemon, bus = await dbus_daemon(monkeypatch)
    helper = sls.dbus.DBusObject(bus, f'{sls.constants.DBUS_ROOT}/helpers/Test')
    props = helper.properties(f'{sls.constants.DBUS_NAME}.Helper')

    assert not await props['LastCollected']

    with open(f'{sls.pending}/test/a.bin', 'w'):
        pass

    await asyncio.sleep(0.001)
    assert not await props['LastCollected']

    await patch_module.collect()
    assert time.time() - typing.cast(int, await props['LastCollected']) <= 1

    await daemon.shutdown()


def test_helper_exceptions():
    try:
        helpers.raise_dbus_error(helpers.HelperResult.OK)
    except Exception:
        assert False
    try:
        helpers.raise_dbus_error(helpers.HelperResult.TRANSIENT_ERROR)
        assert False
    except helpers.TransientError:
        pass
    try:
        helpers.raise_dbus_error(helpers.HelperResult.PERMANENT_ERROR)
        assert False
    except helpers.PermanentError:
        pass
    try:
        helpers.raise_dbus_error(helpers.HelperResult.CLASS_ERROR)
        assert False
    except helpers.ClassError:
        pass
