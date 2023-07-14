# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import configparser
import steamos_log_submitter as sls
import steamos_log_submitter.config as config
import steamos_log_submitter.runner as runner
from . import awaitable, unreachable
from . import count_hits  # NOQA: F401


def setup_conf(monkeypatch, enable=None):
    testconf = configparser.ConfigParser()
    monkeypatch.setattr(config, 'config', testconf)
    localconf = configparser.ConfigParser()

    if enable is not None:
        localconf.add_section('sls')
        localconf.set('sls', 'enable', enable)
    monkeypatch.setattr(config, 'local_config', localconf)


def test_config_missing(monkeypatch, count_hits):
    setup_conf(monkeypatch)
    monkeypatch.setattr(runner, 'collect', count_hits)
    monkeypatch.setattr(runner, 'submit', count_hits)
    sls.trigger()

    assert count_hits.hits == 0


def test_config_off(monkeypatch, count_hits):
    setup_conf(monkeypatch, 'off')
    monkeypatch.setattr(runner, 'collect', count_hits)
    monkeypatch.setattr(runner, 'submit', count_hits)
    sls.trigger()

    assert count_hits.hits == 0


def test_config_invalid(monkeypatch, count_hits):
    setup_conf(monkeypatch, 'foo')
    monkeypatch.setattr(runner, 'collect', count_hits)
    monkeypatch.setattr(runner, 'submit', count_hits)
    sls.trigger()

    assert count_hits.hits == 0


def test_config_on(monkeypatch, count_hits):
    setup_conf(monkeypatch, 'on')
    monkeypatch.setattr(runner, 'collect', awaitable(count_hits))
    monkeypatch.setattr(runner, 'submit', awaitable(count_hits))
    sls.trigger()
    assert count_hits.hits == 2


def test_config_unhandled_collect(monkeypatch, count_hits):
    setup_conf(monkeypatch, 'on')
    monkeypatch.setattr(runner, 'collect', awaitable(unreachable))
    monkeypatch.setattr(runner, 'submit', awaitable(count_hits))
    sls.trigger()
    assert count_hits.hits == 1


def test_config_unhandled_submit(monkeypatch, count_hits):
    setup_conf(monkeypatch, 'on')
    monkeypatch.setattr(runner, 'collect', awaitable(count_hits))
    monkeypatch.setattr(runner, 'submit', awaitable(unreachable))
    sls.trigger()
    assert count_hits.hits == 1
