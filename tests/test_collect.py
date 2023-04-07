# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import configparser
import steamos_log_submitter as sls
import steamos_log_submitter.config as config
from . import count_hits, helper_directory, patch_module, setup_categories, unreachable


def submit(log):
    return True


def test_disable_all(helper_directory, monkeypatch, patch_module):
    testconf = configparser.ConfigParser()
    testconf.add_section('helpers.test')
    testconf.set('helpers.test', 'enable', 'off')
    monkeypatch.setattr(config, 'config', testconf)

    setup_categories(['test'])

    patch_module.submit = unreachable
    patch_module.collect = unreachable
    sls.collect()


def test_disable_collect(helper_directory, monkeypatch, patch_module):
    testconf = configparser.ConfigParser()
    testconf.add_section('helpers.test')
    testconf.set('helpers.test', 'collect', 'off')
    monkeypatch.setattr(config, 'config', testconf)

    setup_categories(['test'])

    patch_module.submit = unreachable
    patch_module.collect = unreachable
    sls.collect()


def test_module(helper_directory, monkeypatch, patch_module, count_hits):
    setup_categories(['test'])

    patch_module.submit = submit
    patch_module.collect = count_hits
    sls.collect()

    assert count_hits.hits


def test_lock(helper_directory, monkeypatch, patch_module, count_hits):
    setup_categories(['test'])

    patch_module.submit = submit
    patch_module.collect = count_hits

    lock = sls.lockfile.Lockfile(f'{sls.pending}/test/.lock')
    lock.lock()
    sls.collect()

    assert not count_hits.hits

    lock.unlock()
    sls.collect()

    assert count_hits.hits


def test_error_continue(helper_directory, monkeypatch, patch_module, count_hits):
    def fail_count(*args, **kwargs):
        count_hits()
        assert count_hits.hits != 1
        return False

    setup_categories(['test', 'test2'])

    patch_module.submit = submit
    patch_module.collect = fail_count
    sls.collect()

    assert count_hits.hits == 2
