# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter as sls

from . import open_shim  # NOQA: F401


def test_read_file_text(open_shim):
    open_shim('text')
    assert sls.util.read_file('') == 'text'


def test_read_file_binary(open_shim):
    open_shim(b'bytes')
    assert sls.util.read_file('', binary=True) == b'bytes'


def test_read_file_none(open_shim):
    open_shim(None)
    assert sls.util.read_file('') is None
