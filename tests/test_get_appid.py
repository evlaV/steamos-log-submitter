# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import pytest
import steamos_log_submitter as sls
from . import open_shim  # NOQA: F401


@pytest.fixture
def build_proc_chain(open_shim):
    def setup(procs):
        def cb(fname):
            if not fname.startswith('/proc/'):
                return None
            pid, fname = fname.split('/', 3)[2:]
            pid = int(pid)
            if pid not in procs:
                return None
            ppid, cmdline = procs[pid]
            if fname == 'stat':
                return f'{pid} ({cmdline[0]}) S {ppid} 0'
            if fname == 'cmdline':
                return '\0'.join(cmdline)
            if fname == 'comm':
                return cmdline[0]
        open_shim.cb(cb)
    return setup


def test_dead_pid(open_shim):
    open_shim.cb(lambda filename: None)
    assert sls.util.get_appid(2) is None


def test_no_reaper(build_proc_chain):
    procs = {
        2:  (1, ['tester'])
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None


def test_reaper(build_proc_chain):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100'])
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) == 100


def test_no_steamlaunch(build_proc_chain):
    procs = {
        2:  (1, ['reaper', 'AppId=100'])
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None


def test_no_appid(build_proc_chain):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch'])
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None


def test_stop_parsing(build_proc_chain):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch', '--', 'AppId=100'])
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(2) is None


def test_parent(build_proc_chain):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100']),
        3:  (2, ['tester'])
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(3) == 100


def test_reaper_parent(build_proc_chain):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100']),
        3:  (2, ['reaper'])
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(3) == 100


def test_parent_parent(build_proc_chain):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100']),
        3:  (2, ['tester']),
        4:  (3, ['tester'])
    }
    build_proc_chain(procs)
    assert sls.util.get_appid(4) == 100
