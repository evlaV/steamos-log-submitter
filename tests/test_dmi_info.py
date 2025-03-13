# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2025 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter as sls

from . import open_shim  # NOQA: F401


def test_valve_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'Valve\n'
        if fname.endswith('/bios_version'):
            return 'F7A0100\n'
        if fname.endswith('/product_name'):
            return 'Jupiter\n'
        if fname.endswith('/board_name'):
            return 'Jupiter\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'Valve',
        'bios': 'F7A0100',
        'product': 'Jupiter',
    }


def test_rog_ally_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ASUSTeK COMPUTER INC.\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'INVALID\n'
        if fname.endswith('/board_name'):
            return 'RC71L\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ASUSTeK COMPUTER INC.',
        'product': 'ROG Ally',
    }


def test_rog_ally_x_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ASUSTeK COMPUTER INC.\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'INVALID\n'
        if fname.endswith('/board_name'):
            return 'RC72LA\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ASUSTeK COMPUTER INC.',
        'product': 'ROG Ally X',
    }


def test_other_asus_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ASUSTeK COMPUTER INC.\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'INVALID\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert not info


def test_legion_go_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'LENOVO\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return '83E1\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'LENOVO',
        'product': 'Legion Go',
    }


def test_legion_go_s_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'LENOVO\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return '83L3\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'LENOVO',
        'product': 'Legion Go S',
    }


def test_other_lenovo_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'LENOVO\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'INVALID\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert not info


def test_zotac_zone_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ZOTAC\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ZOTAC GAMING ZONE\n'
        if fname.endswith('/board_name'):
            return 'G0A1W\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ZOTAC',
        'product': 'ZONE',
    }


def test_other_zotac_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ZOTAC\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ZOTAC GAMING REGION\n'
        if fname.endswith('/board_name'):
            return 'G0Z1W\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert not info


def test_other_vendor_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'DELL\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'INVALID\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert not info
