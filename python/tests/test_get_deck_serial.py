import builtins
import steamos_log_submitter as sls
from . import open_shim

def test_no_vdf(monkeypatch):
    def raise_enoent(*args, **kwargs):
        raise FileNotFoundError(args[0])
    monkeypatch.setattr(builtins, "open", raise_enoent)
    assert not sls.get_deck_serial()


def test_no_serial(monkeypatch):
    vdf = """"InstallConfigStore"
{
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_deck_serial() is None


def test_serial(monkeypatch):
    vdf = """"InstallConfigStore"
{
	"SteamDeckRegisteredSerialNumber"		"Test"
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_deck_serial() == "Test"


def test_invalid_vdf(monkeypatch):
    vdf = "not"
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_deck_serial() is None


def test_invalid_schema(monkeypatch):
    vdf = """"liars"
{
	"SteamDeckRegisteredSerialNumber"		"Test"
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_deck_serial() is None


def test_invalid_schema2(monkeypatch):
    vdf = """"InstallConfigStore"
{
	"SteamDeckRegisteredSerialNumber"
	{
	}
}"""
    monkeypatch.setattr(builtins, "open", open_shim(vdf))
    assert sls.get_deck_serial() is None
