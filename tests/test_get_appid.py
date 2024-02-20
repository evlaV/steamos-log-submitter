# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import pytest
from collections.abc import Mapping, Sequence
from typing import TypeAlias

import steamos_log_submitter as sls
from . import open_shim  # NOQA: F401

ProcChain: TypeAlias = Mapping[int, tuple[int, Sequence[str], Mapping[str, str]]]


@pytest.fixture
def build_proc_chain(open_shim):
    def setup(procs: ProcChain):
        def cb(fname):
            if not fname.startswith('/proc/'):
                return None
            pid, fname = fname.split('/', 3)[2:]
            pid = int(pid)
            if pid not in procs:
                return None
            ppid, cmdline, env = procs[pid]
            if fname == 'stat':
                return f'{pid} ({cmdline[0]}) S {ppid} 0'
            if fname == 'cmdline':
                return '\0'.join(cmdline)
            if fname == 'comm':
                return cmdline[0]
            if fname == 'environ':
                return '\0'.join(f'{k}={v}' for k, v in env.items())
        open_shim.cb(cb)
    return setup


def test_dead_pid(open_shim):
    open_shim.cb(lambda filename: None)
    assert sls.util.get_appid(2) is None


def test_no_reaper(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['tester'], {})
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None


def test_reaper(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100'], {})
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) == 100


def test_no_steamlaunch(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['reaper', 'AppId=100'], {})
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None


def test_no_appid(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['reaper', 'SteamLaunch'], {})
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None


def test_nonsteam_appid(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=3000000000'], {})
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None


def test_invalid_appid(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=G'], {})
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None


def test_stop_parsing(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['reaper', 'SteamLaunch', '--', 'AppId=100'], {})
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None


def test_parent(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100'], {}),
        3:  (2, ['tester'], {})
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(3) == 100


def test_reaper_parent(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100'], {}),
        3:  (2, ['reaper'], {})
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(3) == 100


def test_parent_parent(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100'], {}),
        3:  (2, ['tester'], {}),
        4:  (3, ['tester'], {})
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(4) == 100


def test_environ(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['hl2.exe'], {'SteamGameId': '36'}),
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) == 36


def test_environ_invalid_appid(build_proc_chain):
    procs: ProcChain = {
        2:  (1, ['hl2.exe'], {'SteamGameId': 'Man'}),
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None
