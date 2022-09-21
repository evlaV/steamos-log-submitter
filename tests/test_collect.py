import steamos_log_submitter as sls
from . import helper_directory, patch_module, setup_categories

def submit(log):
    return True


def test_module(helper_directory, monkeypatch, patch_module):
    setup_categories({'test': None})

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
    setup_categories({'test': None})

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
