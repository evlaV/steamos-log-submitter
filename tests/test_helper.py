# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import importlib
import os
import steamos_log_submitter as sls
import steamos_log_submitter.helpers as helpers
from . import helper_directory, mock_config, patch_module, setup_categories  # NOQA: F401


def test_staging_file_rename(helper_directory):
    setup_categories(['test'])
    f = helpers.StagingFile('test', 'foo')
    assert not os.access(f'{sls.pending}/test/foo', os.F_OK)
    assert os.access(f.name, os.F_OK)
    ino = os.stat(f.name).st_ino
    f.close()
    assert os.access(f'{sls.pending}/test/foo', os.F_OK)
    assert not os.access(f.name, os.F_OK)
    assert os.stat(f'{sls.pending}/test/foo').st_ino == ino


def test_staging_file_context_manager(helper_directory):
    setup_categories(['test'])
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
