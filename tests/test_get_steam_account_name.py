import builtins
import steamos_log_submitter as sls
from . import open_shim


def test_no_vdf(monkeypatch):
    def raise_enoent(*args, **kwargs):
        raise FileNotFoundError(args[0])
    monkeypatch.setattr(builtins, "open", raise_enoent)
    assert sls.util.get_steam_account_name() is None


def test_no_users(monkeypatch):
    vdf = """"users"
{
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.util.get_steam_account_name() is None


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
    assert sls.util.get_steam_account_name() is None


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
    assert sls.util.get_steam_account_name() is None


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
    assert sls.util.get_steam_account_name() == 'gordon'


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
    assert sls.util.get_steam_account_name() == 'gordon'


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
    assert sls.util.get_steam_account_name() == 'gordon'


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
    assert sls.util.get_steam_account_name() == 'alyx'


def test_invalid_vdf(monkeypatch):
    vdf = "not"
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.util.get_steam_account_name() is None


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
    assert sls.util.get_steam_account_name() is None


def test_invalid_schema2(monkeypatch):
    vdf = """"users"
{
	"2"
	{
        "AccountName"       "gordon"
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.util.get_steam_account_name() is None

# vim:ts=4:sw=4:et
