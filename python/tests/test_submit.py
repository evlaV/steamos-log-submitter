import os
import threading
import time
import steamos_log_submitter as sls
from . import helper_directory, patch_module, setup_categories

def setup_logs(helper_directory, logs):
    for fname, text in logs.items():
        with open(f'{sls.pending}/{fname}', 'w') as f:
            if text:
                f.write(text)


def test_submit_no_categories(helper_directory):
    sls.submit()


def test_submit_empty(helper_directory):
    setup_categories({'foo': None, 'bar': None, 'baz': None})
    sls.submit()


def test_submit_skip_dot(helper_directory):
    setup_categories({'foo': None})
    setup_logs(helper_directory, {'foo/.skip': ''})
    sls.submit()

    assert os.access(f'{sls.pending}/foo/.skip', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/.skip', os.F_OK)


def test_missing_script(helper_directory):
    setup_categories({'foo': None})
    setup_logs(helper_directory, {'foo/log': ''})
    sls.submit()

    assert os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/log', os.F_OK)


def test_broken_module(helper_directory):
    setup_categories({'test': None})
    setup_logs(helper_directory, {'test/log': ''})
    sls.submit()

    assert os.access(f'{sls.pending}/test/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/log', os.F_OK)


def test_success(helper_directory):
    setup_categories({'foo': '#!/bin/sh\n exit 0\n'})
    setup_logs(helper_directory, {'foo/log': ''})
    sls.submit()

    assert not os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/foo/log', os.F_OK)


def test_failure(helper_directory):
    setup_categories({'foo': '#!/bin/sh\n exit 1\n'})
    setup_logs(helper_directory, {'foo/log': ''})
    sls.submit()

    assert os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/log', os.F_OK)


def test_module_success(helper_directory, monkeypatch, patch_module):
    setup_categories({'test': None})
    setup_logs(helper_directory, {'test/log': ''})

    attempt = 0
    def submit(fname):
        nonlocal attempt
        attempt = 1
        return True

    patch_module.submit = submit
    sls.submit()

    assert not os.access(f'{sls.pending}/test/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/test/log', os.F_OK)
    assert attempt


def test_module_failure(helper_directory, monkeypatch, patch_module):
    setup_categories({'test': None})
    setup_logs(helper_directory, {'test/log': ''})

    attempt = 0
    def submit(fname):
        nonlocal attempt
        attempt = 1
        return False

    patch_module.submit = submit
    sls.submit()

    assert os.access(f'{sls.pending}/test/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/log', os.F_OK)
    assert attempt


def test_filename(helper_directory):
    setup_categories({'foo': f'#!/bin/sh\ntest "$1" == "{sls.pending}/foo/log"\nexit $?\n'})
    setup_logs(helper_directory, {'foo/log': '', 'foo/fail': ''})
    sls.submit()

    assert not os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/foo/log', os.F_OK)

    assert os.access(f'{sls.pending}/foo/fail', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/fail', os.F_OK)


def test_lock(helper_directory):
    setup_categories({'foo': '#!/bin/sh\nsleep 0.3\n'})
    setup_logs(helper_directory, {'foo/log': ''})

    running = 0
    def run():
        nonlocal running
        if running != 0:
            time.sleep(0.05)
            assert os.access(f'{sls.pending}/foo/.lock', os.F_OK)
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

# vim:ts=4:sw=4:et
