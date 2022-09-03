import builtins
import glob
import os
import steamos_log_submitter.helpers.kdump as kdump
from . import open_shim

file_base = f'{os.path.dirname(__file__)}/kdump'

def test_dmesg_parse(monkeypatch):
    with open(f'{file_base}/crash') as f:
        crash_expected = f.read()
    with open(f'{file_base}/stack') as f:
        stack_expected = f.read()
    monkeypatch.setattr(glob, 'glob', lambda x: [f'{file_base}/dmesg'])
    crash, stack = kdump.get_summaries()
    assert crash == crash_expected
    assert stack == stack_expected


def test_get_build_id(monkeypatch):
    os_release = """NAME="SteamOS"
PRETTY_NAME="SteamOS"
ID=holo
BUILD_ID=definitely fake"""
    monkeypatch.setattr(builtins, 'open', open_shim(os_release))
    assert kdump.get_build_id() == 'definitely fake'


def test_no_get_build_id(monkeypatch):
    os_release = """NAME="SteamOS"
PRETTY_NAME="SteamOS"
ID=holo"""
    monkeypatch.setattr(builtins, 'open', open_shim(os_release))
    assert kdump.get_build_id() is None


def test_submit_bad_name():
    assert not kdump.submit('not-a-zip.txt')
