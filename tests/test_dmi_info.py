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


def test_rog_xbox_ally_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ASUSTeK COMPUTER INC.\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'INVALID\n'
        if fname.endswith('/board_name'):
            return 'RC73YA\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ASUSTeK COMPUTER INC.',
        'product': 'ROG Xbox Ally',
    }


def test_rog_xbox_ally_x_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ASUSTeK COMPUTER INC.\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'INVALID\n'
        if fname.endswith('/board_name'):
            return 'RC73XA\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ASUSTeK COMPUTER INC.',
        'product': 'ROG Xbox Ally X',
    }


def test_rog_flow_z13_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ASUSTeK COMPUTER INC.\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'INVALID\n'
        if fname.endswith('/board_name'):
            return 'GZ302EA\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ASUSTeK COMPUTER INC.',
        'product': 'ROG Flow Z13 (2025)',
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


def test_zotac_zone_g1a1w_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ZOTAC\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ZOTAC GAMING ZONE\n'
        if fname.endswith('/board_name'):
            return 'G1A1W\n'
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


def test_anbernic_win600_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'Anbernic\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'Win600\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'Anbernic',
        'product': 'Anbernic Win600',
    }


def test_other_anbernic_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'Anbernic\n'
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


def test_ayaneo_3_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'AYANEO\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'AYANEO 3\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'AYANEO',
        'product': 'AYANEO 3',
    }


def test_ayaneo_air_1s_limited_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'AYANEO\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'AIR 1S Limited\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'AYANEO',
        'product': 'AYANEO AIR 1S Limited',
    }


def test_ayaneo_flip_1s_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'AYANEO\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'FLIP 1S DS\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'AYANEO',
        'product': 'AYANEO FLIP 1S',
    }


def test_gpd_win5_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'GPD\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'G1618-05\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'GPD',
        'product': 'GPD WIN 5',
    }


def test_suiplay_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'MystenLabs, Inc.\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'SuiPlay 0X1\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'MystenLabs, Inc.',
        'product': 'SuiPlay 0X1',
    }


def test_other_mystenlabs_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'MystenLabs, Inc.\n'
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


def test_onexplayer_old_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONEXPLAYER\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK',
        'product': 'ONEXPLAYER',
    }


def test_onexplayer_old_spaced_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONE XPLAYER\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK',
        'product': 'ONEXPLAYER',
    }


def test_onexplayer_old_alt_vendor_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK TECHNOLOGY CO., LTD.\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONE XPLAYER\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK TECHNOLOGY CO., LTD.',
        'product': 'ONEXPLAYER',
    }


def test_onexplayer_mini_a07_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONEXPLAYER mini A07\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK',
        'product': 'ONEXPLAYER mini A07',
    }


def test_onexplayer_onexfly_eva_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONEXPLAYER F1 EVA-01\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK',
        'product': 'ONEXPLAYER OneXFly F1 EVA-01',
    }


def test_onexplayer_onexfly_oled_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONEXPLAYER F1 OLED\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK',
        'product': 'ONEXPLAYER OneXFly F1 OLED',
    }


def test_onexplayer_x1_amd_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONEXPLAYER X1 A\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK',
        'product': 'ONEXPLAYER X1 AMD',
    }


def test_onexplayer_x1_intel_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONEXPLAYER X1 i\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK',
        'product': 'ONEXPLAYER X1 Intel',
    }


def test_onexplayer_x1_mini_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONEXPLAYER X1 mini\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK',
        'product': 'ONEXPLAYER X1 mini',
    }


def test_onexplayer_g1_amd_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONEXPLAYER G1 A\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK',
        'product': 'ONEXPLAYER G1 AMD',
    }


def test_onexplayer_g1_intel_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'ONEXPLAYER G1 i\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'ONE-NETBOOK',
        'product': 'ONEXPLAYER G1 Intel',
    }


def test_other_one_netbook_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'ONE-NETBOOK\n'
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


def test_orangepi_neo_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'OrangePi\n'
        if fname.endswith('/bios_version'):
            return '2\n'
        if fname.endswith('/product_name'):
            return 'NEO-01\n'
        if fname.endswith('/board_name'):
            return 'INVALID\n'
        assert False

    open_shim.cb(fake_dmi)

    info = sls.util.get_dmi_info()
    assert info == {
        'vendor': 'OrangePi',
        'product': 'OrangePi NEO',
    }


def test_other_orangepi_sysinfo(monkeypatch, open_shim):
    def fake_dmi(fname):
        if fname.endswith('/sys_vendor'):
            return 'OrangePi\n'
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
