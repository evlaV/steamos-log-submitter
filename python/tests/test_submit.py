import os
import pytest
import tempfile
import threading
import steamos_log_submitter as sls

@pytest.fixture
def tmpdir(monkeypatch):
    d = tempfile.TemporaryDirectory(prefix='sls-')
    pending = f'{d.name}/pending'
    uploaded = f'{d.name}/uploaded'
    scripts = f'{d.name}/scripts'
    os.mkdir(pending)
    os.mkdir(uploaded)
    os.mkdir(scripts)
    monkeypatch.setattr(sls, 'pending', f'{d.name}/pending')
    monkeypatch.setattr(sls, 'uploaded', f'{d.name}/uploaded')
    monkeypatch.setattr(sls, 'scripts', f'{d.name}/scripts')

    yield d.name

    del d


def setup_categories(tmpdir, categories):
    for category, script in categories.items():
        os.mkdir(f'{sls.pending}/{category}')
        os.mkdir(f'{sls.uploaded}/{category}')
        if script is not None:
            with open(f'{sls.scripts}/{category}', 'w') as f:
                f.write(script)
                os.fchmod(f.fileno(), 0o744)


def setup_logs(tmpdir, logs):
    for fname, text in logs.items():
        with open(f'{sls.pending}/{fname}', 'w') as f:
            if text:
                f.write(text)


def test_submit_no_categories(tmpdir):
    sls.submit()


def test_submit_empty(tmpdir):
    setup_categories(tmpdir, {'foo': None, 'bar': None, 'baz': None})
    sls.submit()


def test_submit_skip_dot(tmpdir):
    setup_categories(tmpdir, {'foo': None})
    setup_logs(tmpdir, {'foo/.skip': ''})
    sls.submit()

    assert os.access(f'{sls.pending}/foo/.skip', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/.skip', os.F_OK)


def test_missing_script(tmpdir):
    setup_categories(tmpdir, {'foo': None})
    setup_logs(tmpdir, {'foo/log': ''})
    sls.submit()

    assert os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/log', os.F_OK)


def test_success(tmpdir):
    setup_categories(tmpdir, {'foo': '#!/bin/sh\n exit 0\n'})
    setup_logs(tmpdir, {'foo/log': ''})
    sls.submit()

    assert not os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/foo/log', os.F_OK)


def test_failure(tmpdir):
    setup_categories(tmpdir, {'foo': '#!/bin/sh\n exit 1\n'})
    setup_logs(tmpdir, {'foo/log': ''})
    sls.submit()

    assert os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/log', os.F_OK)


def test_filename(tmpdir):
    setup_categories(tmpdir, {'foo': f'#!/bin/sh\ntest "$1" == "{sls.pending}/foo/log"\nexit $?\n'})
    setup_logs(tmpdir, {'foo/log': '', 'foo/fail': ''})
    sls.submit()

    assert not os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/foo/log', os.F_OK)

    assert os.access(f'{sls.pending}/foo/fail', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/fail', os.F_OK)


def test_lock(tmpdir):
    setup_categories(tmpdir, {'foo': '#!/bin/sh\nsleep 1\n'})
    setup_logs(tmpdir, {'foo/log': ''})

    running = 0
    def run():
        nonlocal running
        assert running == 0 or os.access(f'{sls.pending}/foo/.lock', os.F_OK)
        running += 1
        sls.submit()

    thread_a = threading.Thread(target=run)
    thread_b = threading.Thread(target=run)

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    assert not os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/foo/log', os.F_OK)
    assert running == 2
