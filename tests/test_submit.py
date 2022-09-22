import configparser
import os
import pytest
import threading
import time
import steamos_log_submitter as sls
import steamos_log_submitter.config as config
from . import helper_directory, patch_module, setup_categories, unreachable

@pytest.fixture
def online(monkeypatch):
    monkeypatch.setattr(sls.util, 'check_network', lambda: True)


def setup_logs(helper_directory, logs):
    for fname, text in logs.items():
        with open(f'{sls.pending}/{fname}', 'w') as f:
            if text:
                f.write(text)


def test_offline(monkeypatch):
    monkeypatch.setattr(sls.util, 'check_network', lambda: False)
    monkeypatch.setattr(os, 'listdir', unreachable)
    sls.submit()


def test_disable_all(helper_directory, monkeypatch, patch_module):
    testconf = configparser.ConfigParser()
    testconf.add_section('helpers.test')
    testconf.set('helpers.test', 'enable', 'off')
    monkeypatch.setattr(config, 'config', testconf)

    setup_categories(['test'])

    patch_module.submit = unreachable
    sls.submit()


def test_disable_submit(helper_directory, monkeypatch, patch_module):
    testconf = configparser.ConfigParser()
    testconf.add_section('helpers.test')
    testconf.set('helpers.test', 'submit', 'off')
    monkeypatch.setattr(config, 'config', testconf)

    setup_categories(['test'])

    patch_module.submit = unreachable
    sls.submit()


def test_submit_no_categories(helper_directory, online):
    sls.submit()


def test_submit_empty(helper_directory, online):
    setup_categories(['foo', 'bar', 'baz'])
    sls.submit()


def test_submit_skip_dot(helper_directory, online):
    setup_categories(['foo'])
    setup_logs(helper_directory, {'foo/.skip': ''})
    sls.submit()

    assert os.access(f'{sls.pending}/foo/.skip', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/.skip', os.F_OK)


def test_missing_module(helper_directory, online):
    setup_categories(['foo'])
    setup_logs(helper_directory, {'foo/log': ''})
    sls.submit()

    assert os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/log', os.F_OK)


def test_broken_module(helper_directory, online):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': ''})
    sls.submit()

    assert os.access(f'{sls.pending}/test/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/log', os.F_OK)


def test_success(helper_directory, online, patch_module):
    setup_categories(['test'])
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


def test_failure(helper_directory, online, patch_module):
    setup_categories(['test'])
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


def test_filename(helper_directory, online, patch_module):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': '', 'test/fail': ''})

    def submit(fname):
        return fname == f'{sls.pending}/test/log'

    patch_module.submit = submit
    sls.submit()

    assert not os.access(f'{sls.pending}/test/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/test/log', os.F_OK)

    assert os.access(f'{sls.pending}/test/fail', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/fail', os.F_OK)


def test_lock(helper_directory, online, patch_module):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': ''})

    def submit(fname):
        time.sleep(0.1)
        return True

    patch_module.submit = submit

    running = 0
    def run():
        nonlocal running
        if running != 0:
            time.sleep(0.05)
            assert os.access(f'{sls.pending}/test/.lock', os.F_OK)
        running += 1
        sls.submit()

    thread_a = threading.Thread(target=run)
    thread_b = threading.Thread(target=run)

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    assert not os.access(f'{sls.pending}/test/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/test/log', os.F_OK)
    assert running == 2

# vim:ts=4:sw=4:et
