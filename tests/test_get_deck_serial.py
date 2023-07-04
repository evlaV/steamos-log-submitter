# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import pwd
from . import always_raise
from . import fake_pwuid, mock_config, open_eacces, open_enoent, open_shim  # NOQA: F401
from steamos_log_submitter.steam import get_deck_serial


def test_no_vdf(monkeypatch):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_enoent)
    assert not get_deck_serial()


def test_eaccess_vdf(monkeypatch):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_eacces)
    assert not get_deck_serial()


def test_config_value(monkeypatch, mock_config):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_enoent)
    mock_config.add_section('steam')
    mock_config.set('steam', 'deck_serial', 'Test')
    assert get_deck_serial() == 'Test'


def test_no_user(monkeypatch):
    monkeypatch.setattr(pwd, "getpwuid", always_raise(KeyError))
    assert get_deck_serial() is None


def test_no_serial(monkeypatch):
    vdf = """"InstallConfigStore"
{
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_deck_serial() is None


def test_serial(monkeypatch):
    vdf = """"InstallConfigStore"
{
	"SteamDeckRegisteredSerialNumber"		"Test"
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_deck_serial() == "Test"


def test_invalid_vdf(monkeypatch):
    vdf = "not"
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_deck_serial() is None


def test_invalid_schema(monkeypatch):
    vdf = """"liars"
{
	"SteamDeckRegisteredSerialNumber"		"Test"
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_deck_serial() is None


def test_invalid_schema2(monkeypatch):
    vdf = """"InstallConfigStore"
{
	"SteamDeckRegisteredSerialNumber"
	{
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_deck_serial() is None
