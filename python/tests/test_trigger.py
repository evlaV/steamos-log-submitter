import io
import subprocess
import steamos_log_submitter as sls

def do_not_hit():
    assert False

def test_inactive_timer(monkeypatch):
    hit = False
    def show_inactive(command, **kwargs):
        nonlocal hit
        if command[1] == 'show' and kwargs.get('stdout', subprocess.DEVNULL) == subprocess.PIPE:
            hit = True
            return subprocess.CompletedProcess(command, 0, stdout=io.BytesIO(b'Thing=\nActiveState=inactive\nOtherThing=\n'))
        assert False

    monkeypatch.setattr(subprocess, 'Popen', show_inactive)
    monkeypatch.setattr(sls, 'submit', do_not_hit)
    sls.trigger()

    assert hit


def test_active_timer(monkeypatch):
    attempt = 0
    def show_active(command, **kwargs):
        nonlocal attempt
        if command[1] == 'show' and kwargs.get('stdout', subprocess.DEVNULL) == subprocess.PIPE:
            attempt = 1
            return subprocess.CompletedProcess(command, 0, stdout=io.BytesIO(b'Thing=\nActiveState=active\nOtherThing=\n'))
        assert False
    def do_hit():
        nonlocal attempt
        assert attempt == 1
        attempt = 2

    monkeypatch.setattr(subprocess, 'Popen', show_active)
    monkeypatch.setattr(sls, 'submit', do_hit)
    sls.trigger()

    assert attempt == 2


def test_broken_timer(monkeypatch):
    hit = False
    def show_missing(command, **kwargs):
        nonlocal hit
        if command[1] == 'show' and kwargs.get('stdout', subprocess.DEVNULL) == subprocess.PIPE:
            hit = True
            return subprocess.CompletedProcess(command, 0, stdout=io.BytesIO(b'Thing=\nOtherThing=\n'))
        assert False

    monkeypatch.setattr(subprocess, 'Popen', show_missing)
    monkeypatch.setattr(sls, 'submit', do_not_hit)
    sls.trigger()

    assert hit


def test_other_timer(monkeypatch):
    hit = False
    def show_other(command, **kwargs):
        nonlocal hit
        if command[1] == 'show' and kwargs.get('stdout', subprocess.DEVNULL) == subprocess.PIPE:
            hit = True
            return subprocess.CompletedProcess(command, 0, stdout=io.BytesIO(b'Thing=\nActiveState=other\nOtherThing=\n'))
        assert False

    monkeypatch.setattr(subprocess, 'Popen', show_other)
    monkeypatch.setattr(sls, 'submit', do_not_hit)
    sls.trigger()

    assert hit

# vim:ts=4:sw=4:et
