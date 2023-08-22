# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter.util as util
from . import open_shim  # NOQA: F401


def test_get_build_id(open_shim):
    os_release = """NAME="SteamOS"
PRETTY_NAME="SteamOS"
ID=holo
BUILD_ID=definitely fake
"""
    open_shim(os_release)
    assert util.get_build_id() == 'definitely fake'


def test_no_get_build_id(open_shim):
    os_release = """NAME="SteamOS"
PRETTY_NAME="SteamOS"
ID=holo
"""
    open_shim(os_release)
    assert util.get_build_id() is None


def test_get_invalid_line(open_shim):
    os_release = """NAME="SteamOS"
PRETTY_NAME="SteamOS"
ID=holo
# Pretend comment
BUILD_ID=definitely fake
"""
    open_shim(os_release)
    assert util.get_build_id() == 'definitely fake'


def test_no_file(open_shim):
    open_shim.enoent()
    assert util.get_build_id() is None


def test_eacces_file(open_shim):
    open_shim.eacces()
    assert util.get_build_id() is None
