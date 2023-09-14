# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import pwd
from . import always_raise
from . import fake_pwuid, mock_config, open_shim  # NOQA: F401
from steamos_log_submitter.steam import get_steam_account_name


def test_no_vdf(monkeypatch, open_shim):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim.enoent()
    assert get_steam_account_name() is None


def test_eacces_vdf(monkeypatch, open_shim):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim.eacces()
    assert get_steam_account_name() is None


def test_config_value(monkeypatch, mock_config, open_shim):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim.enoent()
    mock_config.add_section('steam')
    mock_config.set('steam', 'account_name', 'gordon')
    assert get_steam_account_name() == 'gordon'


def test_no_user(monkeypatch):
    monkeypatch.setattr(pwd, "getpwuid", always_raise(KeyError))
    assert get_steam_account_name() is None


def test_no_users(monkeypatch, open_shim):
    vdf = """"users"
{
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_steam_account_name() is None


def test_no_recent(monkeypatch, open_shim):
    vdf = """"users"
{
	"0"
	{
		"MostRecent"		"0"
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_steam_account_name() is None


def test_no_recent2(monkeypatch, open_shim):
    vdf = """"users"
{
	"0"
	{
		"MostRecent"		"0"
        "AccountName"       "gordon"
	}

	"1"
	{
		"MostRecent"		"0"
        "AccountName"       "alyx"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_steam_account_name() is None


def test_one(monkeypatch, open_shim):
    vdf = """"users"
{
	"2"
	{
		"MostRecent"		"1"
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_steam_account_name() == 'gordon'


def test_lowercase(monkeypatch, open_shim):
    vdf = """"users"
{
	"2"
	{
		"mostrecent"		"1"
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_steam_account_name() == 'gordon'


def test_first_recent(monkeypatch, open_shim):
    vdf = """"users"
{
	"2"
	{
		"MostRecent"		"1"
        "AccountName"       "gordon"
	}

	"3"
	{
		"MostRecent"		"0"
        "AccountName"       "alyx"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_steam_account_name() == 'gordon'


def test_second_recent(monkeypatch, open_shim):
    vdf = """"users"
{
	"2"
	{
		"MostRecent"		"0"
        "AccountName"       "gordon"
	}

	"3"
	{
		"MostRecent"		"1"
        "AccountName"       "alyx"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_steam_account_name() == 'alyx'


def test_invalid_vdf(monkeypatch, open_shim):
    vdf = "not"
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_steam_account_name() is None


def test_invalid_schema(monkeypatch, open_shim):
    vdf = """"liars"
{
	"2"
	{
		"MostRecent"		"1"
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_steam_account_name() is None


def test_invalid_schema2(monkeypatch, open_shim):
    vdf = """"users"
{
	"2"
	{
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    open_shim(vdf)
    assert get_steam_account_name() is None


def test_skip_config(monkeypatch, mock_config, open_shim):
    vdf = """"users"
{
	"2"
	{
		"MostRecent"		"1"
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: pwd.struct_passwd(('', '', uid, uid, '', '/home/deck', '')))
    mock_config.add_section('steam')
    mock_config.set('steam', 'account_name', 'alyx')
    open_shim(vdf)
    assert get_steam_account_name() == 'alyx'
    assert get_steam_account_name(force_vdf=True) == 'gordon'
