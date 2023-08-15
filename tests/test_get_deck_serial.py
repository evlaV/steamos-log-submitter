# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import pwd
from . import always_raise
from . import fake_pwuid, mock_config, open_shim  # NOQA: F401
from steamos_log_submitter.steam import get_deck_serial


def test_no_vdf(monkeypatch, open_shim):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim.enoent()
    assert not get_deck_serial()


def test_eaccess_vdf(monkeypatch, open_shim):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim.eacces()
    assert not get_deck_serial()


def test_config_value(monkeypatch, mock_config, open_shim):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim.enoent()
    mock_config.add_section('steam')
    mock_config.set('steam', 'deck_serial', 'Test')
    assert get_deck_serial() == 'Test'


def test_no_user(monkeypatch):
    monkeypatch.setattr(pwd, "getpwuid", always_raise(KeyError))
    assert get_deck_serial() is None


def test_no_serial(monkeypatch, open_shim):
    vdf = """"InstallConfigStore"
{
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_deck_serial() is None


def test_serial(monkeypatch, open_shim):
    vdf = """"InstallConfigStore"
{
	"SteamDeckRegisteredSerialNumber"		"Test"
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_deck_serial() == "Test"


def test_invalid_vdf(monkeypatch, open_shim):
    vdf = "not"
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_deck_serial() is None


def test_invalid_schema(monkeypatch, open_shim):
    vdf = """"liars"
{
	"SteamDeckRegisteredSerialNumber"		"Test"
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_deck_serial() is None


def test_invalid_schema2(monkeypatch, open_shim):
    vdf = """"InstallConfigStore"
{
	"SteamDeckRegisteredSerialNumber"
	{
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_deck_serial() is None
