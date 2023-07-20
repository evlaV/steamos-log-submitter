# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter.steam as steam
from . import mock_config  # NOQA: F401


def test_default_uid_default(mock_config):
    mock_config.add_section('steam')
    assert not mock_config.has_option('steam', 'uid')
    steam._setup()
    assert steam.default_uid == 1000


def test_default_uid_config(mock_config):
    mock_config.add_section('steam')
    mock_config.set('steam', 'uid', '2000')
    steam._setup()
    assert steam.default_uid == 2000


def test_default_uid_bad_config(mock_config):
    mock_config.add_section('steam')
    mock_config.set('steam', 'uid', 'mossman')
    steam._setup()
    assert steam.default_uid == 1000
