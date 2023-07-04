# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import pwd
from . import always_raise
from . import fake_pwuid, mock_config, open_eacces, open_enoent, open_shim  # NOQA: F401
from steamos_log_submitter.steam import get_steam_account_id


def test_no_vdf(monkeypatch):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_enoent)
    assert get_steam_account_id() is None


def test_eacces_vdf(monkeypatch):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_eacces)
    assert get_steam_account_id() is None


def test_config_value(monkeypatch, mock_config):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_enoent)
    mock_config.add_section('steam')
    mock_config.set('steam', 'account_id', '1')
    assert get_steam_account_id() == 1


def test_config_invalid_value(monkeypatch, mock_config):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_enoent)
    mock_config.add_section('steam')
    mock_config.set('steam', 'account_id', 'foo')
    assert get_steam_account_id() is None


def test_no_user(monkeypatch):
    monkeypatch.setattr(pwd, "getpwuid", always_raise(KeyError))
    assert get_steam_account_id() is None


def test_no_users(monkeypatch):
    vdf = """"users"
{
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_id() is None


def test_no_recent(monkeypatch):
    vdf = """"users"
{
	"0"
	{
		"MostRecent"		"0"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_id() is None


def test_no_recent2(monkeypatch):
    vdf = """"users"
{
	"0"
	{
		"MostRecent"		"0"
	}

	"1"
	{
		"MostRecent"		"0"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_id() is None


def test_one(monkeypatch):
    vdf = """"users"
{
	"2"
	{
		"MostRecent"		"1"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_id() == 2


def test_lowercase(monkeypatch):
    vdf = """"users"
{
	"2"
	{
		"mostrecent"		"1"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_id() == 2


def test_first_recent(monkeypatch):
    vdf = """"users"
{
	"2"
	{
		"MostRecent"		"1"
	}

	"3"
	{
		"MostRecent"		"0"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_id() == 2


def test_second_recent(monkeypatch):
    vdf = """"users"
{
	"2"
	{
		"MostRecent"		"0"
	}

	"3"
	{
		"MostRecent"		"1"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_id() == 3


def test_invalid_vdf(monkeypatch):
    vdf = "not"
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_id() is None


def test_invalid_schema(monkeypatch):
    vdf = """"liars"
{
	"2"
	{
		"MostRecent"		"1"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_id() is None


def test_invalid_schema2(monkeypatch):
    vdf = """"users"
{
	"2"
	{
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_id() is None
