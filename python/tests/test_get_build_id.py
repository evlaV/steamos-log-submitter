import builtins
import steamos_log_submitter.util as util
from . import open_shim

def test_get_build_id(monkeypatch):
    os_release = """NAME="SteamOS"
PRETTY_NAME="SteamOS"
ID=holo
BUILD_ID=definitely fake
"""
    monkeypatch.setattr(builtins, 'open', open_shim(os_release))
    assert util.get_build_id() == 'definitely fake'


def test_no_get_build_id(monkeypatch):
    os_release = """NAME="SteamOS"
PRETTY_NAME="SteamOS"
ID=holo
"""
    monkeypatch.setattr(builtins, 'open', open_shim(os_release))
    assert util.get_build_id() is None


