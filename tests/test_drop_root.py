# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import grp
import os
import pwd
import pytest
import steamos_log_submitter as sls
from . import always_raise


@pytest.fixture
def fake_id(monkeypatch):
    uid = 0
    gid = 0

    def seteuid(id):
        nonlocal uid
        uid = id

    def setegid(id):
        nonlocal gid
        if id != gid and uid != 0:
            raise PermissionError
        gid = id

    monkeypatch.setattr(os, 'geteuid', lambda: uid)
    monkeypatch.setattr(os, 'getegid', lambda: gid)
    monkeypatch.setattr(os, 'seteuid', seteuid)
    monkeypatch.setattr(os, 'setegid', setegid)
    monkeypatch.setattr(pwd, 'getpwnam', lambda _: (None, None, 1000))
    monkeypatch.setattr(grp, 'getgrnam', lambda _: (None, None, 1000))


def test_drop(fake_id):
    assert os.geteuid() == 0
    assert os.getegid() == 0

    with sls.util.drop_root():
        assert os.geteuid() == 1000
        assert os.getegid() == 1000

    assert os.geteuid() == 0
    assert os.getegid() == 0


def test_already_sls(fake_id):
    os.setegid(1000)
    os.seteuid(1000)

    assert os.geteuid() == 1000
    assert os.getegid() == 1000

    with sls.util.drop_root():
        assert os.geteuid() == 1000
        assert os.getegid() == 1000

    assert os.geteuid() == 1000
    assert os.getegid() == 1000


def test_drop_fail(fake_id, monkeypatch):
    monkeypatch.setattr(os, 'seteuid', always_raise(PermissionError))
    monkeypatch.setattr(os, 'setegid', always_raise(PermissionError))

    try:
        with sls.util.drop_root():
            assert False
    except PermissionError:
        pass
    except Exception:
        assert False

    assert os.geteuid() == 0
    assert os.getegid() == 0
