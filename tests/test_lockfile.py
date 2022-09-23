import builtins
import os
import pytest
from steamos_log_submitter.lockfile import Lockfile, LockHeldError, LockNotHeldError


@pytest.fixture(scope='function')
def lockfile():
    try:
        os.remove('.tmp.lock')
    except FileNotFoundError:
        pass

    yield '.tmp.lock'

    try:
        os.remove('.tmp.lock')
    except FileNotFoundError:
        pass


def test_uncontended_open(lockfile):
    lock = Lockfile(lockfile)
    assert lock
    assert lock._path == lockfile
    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)

    lock.lock()
    assert lock.lockfile
    assert os.access(lock._path, os.F_OK)

    lock.unlock()
    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)


def test_invalid_unlock(lockfile):
    lock = Lockfile(lockfile)
    assert lock
    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)

    try:
        lock.unlock()
    except LockNotHeldError:
        return
    assert False


def test_double_lock(lockfile):
    lock = Lockfile(lockfile)
    assert lock
    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)

    lock.lock()
    assert lock.lockfile
    assert os.access(lock._path, os.F_OK)

    lock.lock()
    assert lock.lockfile
    assert os.access(lock._path, os.F_OK)


def test_invalid_unlock_deletion(lockfile):
    lock = Lockfile(lockfile)
    assert lock
    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)

    with open(lock._path, 'w'):
        pass
    assert os.access(lock._path, os.F_OK)

    try:
        lock.unlock()
    except LockNotHeldError:
        assert os.access(lock._path, os.F_OK)
        return
    assert False


def test_context(lockfile):
    lock = Lockfile(lockfile)
    assert lock
    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)

    with lock:
        assert lock.lockfile
        assert os.access(lock._path, os.F_OK)

    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)


def test_early_unlock(lockfile):
    lock = Lockfile(lockfile)
    assert lock
    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)

    hit = 0
    try:
        with lock:
            assert lock.lockfile
            assert os.access(lock._path, os.F_OK)

            lock.unlock()
            assert not lock.lockfile
            assert not os.access(lock._path, os.F_OK)
            hit += 1
    except LockNotHeldError:
        hit += 1

    assert hit == 2

    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)


def test_context_exceptions(lockfile):
    lock = Lockfile(lockfile)
    assert lock

    try:
        with lock:
            raise RuntimeError
    except RuntimeError:
        return
    assert False


def test_content(lockfile):
    lock = Lockfile(lockfile)
    assert lock

    with lock:
        with open(lockfile, 'r') as f:
            content = f.read()
        assert content
        pathinfo = content.split('/')
        assert len(pathinfo) == 5
        assert not pathinfo[0]
        assert pathinfo[1] == 'proc'
        assert pathinfo[2] == str(os.getpid())
        assert pathinfo[3] == 'fd'
        assert pathinfo[4] == str(lock.lockfile.fileno())
        assert os.readlink(content) == os.path.realpath(lockfile)


def test_contended_open(lockfile):
    lock_a = Lockfile(lockfile)
    lock_b = Lockfile(lockfile)

    assert lock_a
    assert lock_b
    assert not lock_a.lockfile
    assert not lock_b.lockfile

    with lock_a:
        assert lock_a.lockfile
        assert not lock_b.lockfile
        try:
            with lock_b:
                assert False
        except LockHeldError:
            pass
        except:
            assert False
        assert lock_a.lockfile
        assert not lock_b.lockfile
        assert os.access(lock_a._path, os.F_OK)


def test_invalid_lock(lockfile):
    with open(lockfile, 'w') as f:
        f.write('liar')

    lock = Lockfile(lockfile)
    with lock:
        assert lock.lockfile


def test_enoent_lock(lockfile):
    with open(lockfile, 'w') as f:
        f.write('/proc/Z/fd/0')

    lock = Lockfile(lockfile)
    with lock:
        assert lock.lockfile


def test_eperm_lock(lockfile):
    with open(lockfile, 'w') as f:
        f.write('/proc/1/fd/0')

    lock = Lockfile(lockfile)
    with lock:
        assert lock.lockfile


def test_stale_lock(lockfile):
    with open(lockfile, 'w') as f:
        f.write(f'/proc/{os.getpid()}/fd/0')

    lock = Lockfile(lockfile)
    with lock:
        assert lock.lockfile


def test_disappearing_contention(lockfile, monkeypatch):
    attempt = 0
    real_open = open

    def open_fake(fname, mode):
        nonlocal attempt
        if mode == 'x' and attempt == 0:
            raise FileExistsError
        if mode == 'r':
            attempt = 1
            raise FileNotFoundError
        return real_open(fname, mode)

    monkeypatch.setattr(builtins, 'open', open_fake)

    lock = Lockfile(lockfile)
    assert lock
    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)

    with lock:
        assert lock.lockfile
        assert os.access(lock._path, os.F_OK)

    assert not lock.lockfile
    assert not os.access(lock._path, os.F_OK)


def test_slow_lockinfo(lockfile, monkeypatch):
    attempt = 0
    real_open = open

    def open_fake(*args):
        f = real_open(*args)
        real_read = f.read

        def read_fake(*args):
            nonlocal attempt
            if attempt < 2:
                attempt += 1
                return None
            f.read = real_read
            return f.read()
        f.read = read_fake
        return f

    monkeypatch.setattr(builtins, 'open', open_fake)

    lock_a = Lockfile(lockfile)
    lock_b = Lockfile(lockfile)

    assert lock_a
    assert lock_b
    assert not lock_a.lockfile
    assert not lock_b.lockfile

    with lock_a:
        assert lock_a.lockfile
        assert not lock_b.lockfile
        try:
            with lock_b:
                assert False
        except LockHeldError:
            pass
        except:
            assert False
        assert lock_a.lockfile
        assert not lock_b.lockfile
        assert os.access(lock_a._path, os.F_OK)


def test_very_slow_lockinfo(lockfile, monkeypatch):
    attempt = 0
    real_open = open

    def open_fake(*args):
        f = real_open(*args)
        real_read = f.read

        def read_fake(*args):
            nonlocal attempt
            if attempt < 4:
                attempt += 1
                return None
            f.read = real_read
            return f.read()
        f.read = read_fake
        return f

    monkeypatch.setattr(builtins, 'open', open_fake)

    lock_a = Lockfile(lockfile)
    lock_b = Lockfile(lockfile)

    assert lock_a
    assert lock_b
    assert not lock_a.lockfile
    assert not lock_b.lockfile

    with lock_a:
        assert lock_a.lockfile
        assert not lock_b.lockfile
        try:
            with lock_b:
                assert False
        except LockHeldError:
            pass
        except:
            assert False
        assert lock_a.lockfile
        assert not lock_b.lockfile
        assert os.access(lock_a._path, os.F_OK)

# vim:ts=4:sw=4:et
