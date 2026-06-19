# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2026 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import os
import steamos_log_submitter as sls

file_base = f'{os.path.dirname(__file__)}'


def test_get_exe_build_id_good():
    assert sls.util.get_exe_build_id(f'{file_base}/buildid.elf') == 'ffe724b91a1a7f6836d9602d80d1296bad4e4e8c'


def test_get_exe_build_id_missing():
    assert sls.util.get_exe_build_id(f'{file_base}/nothing.elf') is None


def test_get_exe_build_id_not_elf():
    assert sls.util.get_exe_build_id(__file__) is None
