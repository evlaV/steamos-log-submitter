import configparser
import steamos_log_submitter as sls
import steamos_log_submitter.config as config
from . import helper_directory, patch_module, setup_categories, unreachable

def submit(log):
    return True


def test_disable_all(helper_directory, monkeypatch, patch_module):
    testconf = configparser.ConfigParser()
    testconf.add_section('helpers.test')
    testconf.set('helpers.test', 'enable', 'off')
    monkeypatch.setattr(config, 'config', testconf)

    setup_categories(['test'])

    patch_module.submit = unreachable
    patch_module.collect = unreachable
    sls.collect()


def test_disable_collect(helper_directory, monkeypatch, patch_module):
    testconf = configparser.ConfigParser()
    testconf.add_section('helpers.test')
    testconf.set('helpers.test', 'collect', 'off')
    monkeypatch.setattr(config, 'config', testconf)

    setup_categories(['test'])

    patch_module.submit = unreachable
    patch_module.collect = unreachable
    sls.collect()


def test_module(helper_directory, monkeypatch, patch_module):
    setup_categories(['test'])

    attempt = 0
    def collect():
        nonlocal attempt
        attempt = 1
        return False

    patch_module.submit = submit
    patch_module.collect = collect
    sls.collect()

    assert attempt


def test_lock(helper_directory, monkeypatch, patch_module):
    setup_categories(['test'])

    attempt = 0
    def collect():
        nonlocal attempt
        attempt = 1
        return False

    patch_module.submit = submit
    patch_module.collect = collect

    lock = sls.lockfile.Lockfile(f'{sls.pending}/test/.lock')
    lock.lock()
    sls.collect()
    lock.unlock()

    assert not attempt

    sls.collect()

    assert attempt

# vim:ts=4:sw=4:et
