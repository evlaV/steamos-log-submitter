# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import re
import steamos_log_submitter as sls
from . import open_shim  # NOQA: F401


def test_no_account_info(open_shim):
    open_shim.eacces()
    assert sls.util.telemetry_unit_id() is None

    def check_file(fname):
        return b'12345678'

    open_shim.cb(check_file)
    assert sls.util.telemetry_unit_id() is not None

    assert sls.util.telemetry_unit_id() is not None
    assert id != sls.util.telemetry_unit_id()


def test_hex(open_shim):
    def check_file(fname):
        return b'12345678'

    open_shim.cb(check_file)

    unit_id = sls.util.telemetry_unit_id()

    assert unit_id
    assert len(unit_id) == 32
    assert re.match('^[0-9a-f]*$', unit_id)


def test_salt_unit(open_shim):
    addr = b'12345678'
    other = b'12345678'

    def check_file(fname):
        if fname.endswith('address'):
            return addr
        return other

    open_shim.cb(check_file)

    ids = {sls.util.telemetry_unit_id()}

    addr = b'12345679'
    other = b'12345678'
    ids.add(sls.util.telemetry_unit_id())

    addr = b'12345678'
    other = b'12345679'
    ids.add(sls.util.telemetry_unit_id())

    assert len(ids) == 3
