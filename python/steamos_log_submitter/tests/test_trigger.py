import io
import subprocess
import steamos_log_submitter as sls

def test_inactive_timer(monkeypatch):
    def show_inactive(command, **kwargs):
        if command[1] == 'show' and kwargs.get('stdout', subprocess.DEVNULL) == subprocess.PIPE:
            return subprocess.CompletedProcess(command, 0, stdout=io.BytesIO(b'ActiveState=inactive\n'))
        assert False

    monkeypatch.setattr(subprocess, 'Popen', show_inactive)
    sls.trigger()


def test_active_timer(monkeypatch):
    attempt = 0
    def show_inactive(command, **kwargs):
        nonlocal attempt
        if command[1] == 'show' and kwargs.get('stdout', subprocess.DEVNULL) == subprocess.PIPE:
            attempt = 1
            return subprocess.CompletedProcess(command, 0, stdout=io.BytesIO(b'ActiveState=active\n'))
        if command[1] == 'start' and attempt == 1:
            attempt = 2
            return
        assert False

    monkeypatch.setattr(subprocess, 'Popen', show_inactive)
    sls.trigger()

    assert attempt == 2
