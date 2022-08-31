import builtins
import steamos_log_submitter as sls
from . import open_shim_cb

def build_proc_chain(procs):
    def cb(fname):
        if not fname.startswith('/proc/'):
            return None
        pid, fname = fname.split('/', 3)[2:]
        pid = int(pid)
        if pid not in procs:
            return None
        ppid, cmdline = procs[pid]
        if fname == 'stat':
            return  f'{pid} ({cmdline[0]}) S {ppid} 0'
        if fname == 'cmdline':
            return '\0'.join(cmdline)
        if fname == 'comm':
            return cmdline[0]
    return open_shim_cb(cb)


def test_dead_pid(monkeypatch):
    def cb(fname):
        return None
    monkeypatch.setattr(builtins, "open", open_shim_cb(cb))
    assert sls.get_appid(2) is None


def test_no_reaper(monkeypatch):
    procs = {
        2:  (1, ['tester'])
    }
    monkeypatch.setattr(builtins, "open", build_proc_chain(procs))
    assert sls.get_appid(2) is None


def test_reaper(monkeypatch):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100'])
    }
    monkeypatch.setattr(builtins, "open", build_proc_chain(procs))
    assert sls.get_appid(2) == 100


def test_no_steamlaunch(monkeypatch):
    procs = {
        2:  (1, ['reaper', 'AppId=100'])
    }
    monkeypatch.setattr(builtins, "open", build_proc_chain(procs))
    assert sls.get_appid(2) is None


def test_no_appid(monkeypatch):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch'])
    }
    monkeypatch.setattr(builtins, "open", build_proc_chain(procs))
    assert sls.get_appid(2) is None


def test_stop_parsing(monkeypatch):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch', '--', 'AppId=100'])
    }
    monkeypatch.setattr(builtins, "open", build_proc_chain(procs))
    assert sls.get_appid(2) is None


def test_parent(monkeypatch):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100']),
        3:  (2, ['tester'])
    }
    monkeypatch.setattr(builtins, "open", build_proc_chain(procs))
    assert sls.get_appid(3) == 100


def test_reaper_parent(monkeypatch):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100']),
        3:  (2, ['reaper'])
    }
    monkeypatch.setattr(builtins, "open", build_proc_chain(procs))
    assert sls.get_appid(3) == 100


def test_parent_parent(monkeypatch):
    procs = {
        2:  (1, ['reaper', 'SteamLaunch', 'AppId=100']),
        3:  (2, ['tester']),
        4:  (3, ['tester'])
    }
    monkeypatch.setattr(builtins, "open", build_proc_chain(procs))
    assert sls.get_appid(4) == 100
