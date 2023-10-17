# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import re
import steamos_log_submitter as sls
from . import mock_config, open_shim  # NOQA: F401


def test_no_account_info(mock_config, open_shim):
    mock_config.add_section('steam')
    open_shim.eacces()
    assert sls.util.telemetry_user_id() is None
    assert sls.util.telemetry_unit_id() is None

    mock_config.set('steam', 'deck_serial', 'FVAA')
    open_shim.eacces()
    assert sls.util.telemetry_user_id() is None
    assert sls.util.telemetry_unit_id() is None
    mock_config.remove_option('steam', 'deck_serial')

    mock_config.set('steam', 'deck_serial', 'FVAA')
    open_shim.eacces()
    assert sls.util.telemetry_user_id() is None
    assert sls.util.telemetry_unit_id() is None
    mock_config.remove_option('steam', 'deck_serial')

    def check_file(fname):
        if fname.endswith('.vdf'):
            return None
        return b'12345678'

    open_shim.cb(check_file)
    assert sls.util.telemetry_user_id() is None
    assert sls.util.telemetry_unit_id() is not None
    id = sls.util.telemetry_unit_id()

    mock_config.set('steam', 'deck_serial', 'FVAA')
    open_shim.cb(check_file)
    assert sls.util.telemetry_user_id() is None
    assert sls.util.telemetry_unit_id() is not None
    assert id != sls.util.telemetry_unit_id()
    mock_config.remove_option('steam', 'account_name')

    mock_config.set('steam', 'account_id', '1')
    open_shim.eacces()
    assert sls.util.telemetry_user_id() is None
    assert sls.util.telemetry_unit_id() is None
    mock_config.remove_option('steam', 'account_id')

    mock_config.set('steam', 'account_name', 'gaben')
    mock_config.set('steam', 'account_id', '1')
    open_shim.eacces()
    assert sls.util.telemetry_user_id() is not None
    assert sls.util.telemetry_unit_id() is None


def test_hex(mock_config, open_shim):
    def check_file(fname):
        if fname.endswith('.vdf'):
            return None
        return b'12345678'

    open_shim.cb(check_file)
    mock_config.add_section('steam')
    mock_config.set('steam', 'deck_serial', 'FVAA')
    mock_config.set('steam', 'account_name', 'gaben')
    mock_config.set('steam', 'account_id', '1')

    user_id = sls.util.telemetry_user_id()
    unit_id = sls.util.telemetry_unit_id()

    assert user_id
    assert unit_id
    assert len(user_id) == 32
    assert len(unit_id) == 32
    assert re.match('^[0-9a-f]*$', user_id)
    assert re.match('^[0-9a-f]*$', unit_id)


def test_salt_user(mock_config):
    mock_config.add_section('steam')
    mock_config.set('steam', 'account_name', 'gaben')
    mock_config.set('steam', 'account_id', '1')

    ids = {sls.util.telemetry_user_id()}

    mock_config.set('steam', 'account_name', 'gabey')
    mock_config.set('steam', 'account_id', '1')
    ids.add(sls.util.telemetry_user_id())

    mock_config.set('steam', 'account_name', 'gaben')
    mock_config.set('steam', 'account_id', '2')
    ids.add(sls.util.telemetry_user_id())

    assert len(ids) == 3


def test_salt_unit(mock_config, open_shim):
    mock_config.add_section('steam')
    mock_config.set('steam', 'deck_serial', 'FVAA00000001')
    open_shim(b'12:34:56:78:9A:BC')

    ids = {sls.util.telemetry_unit_id()}

    mock_config.set('steam', 'deck_serial', 'FVAA00000002')
    open_shim(b'12:34:56:78:9A:BC')
    ids.add(sls.util.telemetry_unit_id())

    mock_config.set('steam', 'deck_serial', 'FVAA00000001')
    open_shim(b'12:34:56:78:9A:BD')
    ids.add(sls.util.telemetry_unit_id())

    assert len(ids) == 3
