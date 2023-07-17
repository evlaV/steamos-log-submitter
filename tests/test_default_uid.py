# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import sys
import steamos_log_submitter as sls
from . import mock_config  # NOQA: F401


def test_default_uid_default(mock_config, monkeypatch):
    monkeypatch.delitem(sys.modules, 'steamos_log_submitter.steam')
    monkeypatch.delattr(sls, 'steam')
    mock_config.add_section('steam')
    assert not mock_config.has_option('steam', 'uid')
    import steamos_log_submitter.steam as steam
    assert steam.default_uid == 1000


def test_default_uid_config(mock_config, monkeypatch):
    monkeypatch.delitem(sys.modules, 'steamos_log_submitter.steam')
    monkeypatch.delattr(sls, 'steam')
    mock_config.add_section('steam')
    mock_config.set('steam', 'uid', '2000')
    import steamos_log_submitter.steam as steam
    assert steam.default_uid == 2000


def test_default_uid_bad_config(mock_config, monkeypatch):
    monkeypatch.delitem(sys.modules, 'steamos_log_submitter.steam')
    monkeypatch.delattr(sls, 'steam')
    mock_config.add_section('steam')
    mock_config.set('steam', 'uid', 'mossman')
    import steamos_log_submitter.steam as steam
    assert steam.default_uid == 1000
