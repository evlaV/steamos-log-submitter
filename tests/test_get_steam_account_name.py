# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import steamos_log_submitter as sls
from . import fake_pwuid, mock_config, open_eacces, open_enoent, open_shim
from steamos_log_submitter.steam import get_steam_account_name

from steamos_log_submitter.steam import get_steam_account_id


def test_no_vdf(monkeypatch):
    monkeypatch.setattr(builtins, "open", open_enoent)
    assert get_steam_account_name() is None


def test_eacces_vdf(monkeypatch):
    monkeypatch.setattr(builtins, "open", open_eacces)
    assert get_steam_account_name() is None


def test_config_value(monkeypatch, mock_config):
    monkeypatch.setattr(builtins, "open", open_enoent)
    mock_config.add_section('steam')
    mock_config.set('steam', 'account_name', 'gordon')
    assert get_steam_account_name() == 'gordon'


def test_no_users(monkeypatch):
    vdf = """"users"
{
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_name() is None


def test_no_recent(monkeypatch):
    vdf = """"users"
{
	"0"
	{
		"MostRecent"		"0"
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_name() is None


def test_no_recent2(monkeypatch):
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
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_name() is None


def test_one(monkeypatch):
    vdf = """"users"
{
	"2"
	{
		"MostRecent"		"1"
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_name() == 'gordon'


def test_lowercase(monkeypatch):
    vdf = """"users"
{
	"2"
	{
		"mostrecent"		"1"
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_name() == 'gordon'


def test_first_recent(monkeypatch):
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
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_name() == 'gordon'


def test_second_recent(monkeypatch):
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
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_name() == 'alyx'


def test_invalid_vdf(monkeypatch):
    vdf = "not"
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_name() is None


def test_invalid_schema(monkeypatch):
    vdf = """"liars"
{
	"2"
	{
		"MostRecent"		"1"
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_name() is None


def test_invalid_schema2(monkeypatch):
    vdf = """"users"
{
	"2"
	{
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert get_steam_account_name() is None
