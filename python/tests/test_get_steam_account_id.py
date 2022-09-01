import builtins
import steamos_log_submitter as sls
from . import open_shim

def test_no_vdf(monkeypatch):
    def raise_enoent(*args, **kwargs):
        raise FileNotFoundError(args[0])
    monkeypatch.setattr(builtins, "open", raise_enoent)
    assert not sls.get_steam_account_id()


def test_no_users(monkeypatch):
    vdf = """"users"
{
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_steam_account_id() is None


def test_no_recent(monkeypatch):
    vdf = """"users"
{
	"0"
	{
		"MostRecent"		"0"
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_steam_account_id() is None


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
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_steam_account_id() is None


def test_one(monkeypatch):
    vdf = """"users"
{
	"2"
	{
		"MostRecent"		"1"
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_steam_account_id() == 2


def test_lowercase(monkeypatch):
    vdf = """"users"
{
	"2"
	{
		"mostrecent"		"1"
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_steam_account_id() == 2


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
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_steam_account_id() == 2


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
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_steam_account_id() == 3


def test_invalid_vdf(monkeypatch):
    vdf = "not"
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_steam_account_id() is None


def test_invalid_schema(monkeypatch):
    vdf = """"liars"
{
	"2"
	{
		"MostRecent"		"1"
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_steam_account_id() is None


def test_invalid_schema2(monkeypatch):
    vdf = """"users"
{
	"2"
	{
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_steam_account_id() is None
