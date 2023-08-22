#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import collections
import io
import os
import shutil
import subprocess
import sys

import steamos_log_submitter as sls
import steamos_log_submitter.hooks.coredump as hook

from .. import always_raise, unreachable
from .. import count_hits  # NOQA: F401


def test_tee_basic():
    out = io.BytesIO(b'a' * 4095 + b'b' * 4097)
    in_a = collections.namedtuple('Popen', ['stdin', 'wait'])
    in_b = collections.namedtuple('Popen', ['stdin', 'wait'])

    in_a.stdin = io.BytesIO()
    in_a.stdin.close = lambda: None
    in_a.wait = lambda _: None

    in_b.stdin = io.BytesIO()
    in_b.stdin.close = lambda: None
    in_b.wait = lambda _: None

    hook.tee(out, (in_a, in_b))

    assert in_a.stdin.getvalue() == out.getvalue()
    assert in_b.stdin.getvalue() == out.getvalue()


def test_tee_missing_stdin():
    out = io.BytesIO(b'a' * 4095 + b'b' * 4097)
    in_a = collections.namedtuple('Popen', ['stdin', 'wait'])
    in_b = collections.namedtuple('Popen', ['stdin', 'wait'])

    in_a.stdin = None
    in_a.wait = lambda _: None

    in_b.stdin = io.BytesIO()
    in_b.stdin.close = lambda: None
    in_b.wait = lambda _: None

    hook.tee(out, (in_a, in_b))

    assert in_a.stdin is None
    assert in_b.stdin.getvalue() == out.getvalue()


def test_tee_broken_in():
    out = io.BytesIO(b'a' * 4095 + b'b' * 4097)
    in_a = collections.namedtuple('Popen', ['stdin', 'wait'])
    in_b = collections.namedtuple('Popen', ['stdin', 'wait'])

    in_a.stdin = io.BytesIO()
    in_a.stdin.close = lambda: None
    in_a.stdin.write = always_raise(OSError)
    in_a.wait = lambda _: None

    in_b.stdin = io.BytesIO()
    in_b.stdin.close = lambda: None
    in_b.wait = lambda _: None

    hook.tee(out, (in_a, in_b))

    assert in_a.stdin.getvalue() == b''
    assert in_b.stdin.getvalue() == out.getvalue()


def test_tee_broken_close(count_hits):
    out = io.BytesIO(b'a' * 4095 + b'b' * 4097)
    in_a = collections.namedtuple('Popen', ['stdin', 'wait'])

    in_a.stdin = io.BytesIO()
    in_a.stdin.close = always_raise(OSError)
    in_a.wait = count_hits
    hook.tee(out, (in_a,))

    assert in_a.stdin.getvalue() == out.getvalue()
    assert count_hits.hits == 1


def test_should_collect():
    assert hook.should_collect('/usr/bin/true')
    assert hook.should_collect('/usr/lib/Xorg')
    assert hook.should_collect('/tmp/virus')
    assert not hook.should_collect('/tmp/.mount_not_a_virus')
    assert hook.should_collect('/home/deck/.local/bin/ruby')
    assert not hook.should_collect('/home/deck/.local/share/Steam/ubuntu12_64/secret')
    assert not hook.should_collect('/app/bin/ikea')


def test_basic(monkeypatch):
    attempt = 0
    tmpfile = f'{sls.pending}/minidump/.staging-1-e-P-None.dmp'

    def fake_subprocess(*args, **kwargs):
        nonlocal attempt
        ret = subprocess.CompletedProcess(args[0], 0)
        ret.stdin = io.BytesIO()
        assert attempt < 2
        if attempt == 0:
            assert args[0] == ['/usr/lib/systemd/systemd-coredump', 'P', 'u', 'g', 's', '1', 'c', 'h']
        elif attempt == 1:
            assert args[0] == ['/usr/lib/breakpad/core_handler', 'P', tmpfile]
        attempt += 1
        return ret

    def setxattr(filename, name, value):
        assert filename == tmpfile
        if name == 'user.executable':
            assert value == b'f'
        elif name == 'user.comm':
            assert value == b'e'
        elif name == 'user.path':
            assert value == b'E'
        else:
            assert False

    monkeypatch.setattr(hook, 'tee', lambda *_: None)
    monkeypatch.setattr(os, 'rename', lambda *_: None)
    monkeypatch.setattr(os, 'setxattr', setxattr)
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'Popen', fake_subprocess)
    monkeypatch.setattr(sys, 'argv', ['python', 'P', 'e', 'u', 'g', 's', '1', 'c', 'h', 'f', 'E'])

    assert hook.run()


def test_broken_xattr(monkeypatch, count_hits):
    def fake_subprocess(*args, **kwargs):
        ret = subprocess.CompletedProcess(args[0], 0)
        ret.stdin = io.BytesIO()
        return ret

    monkeypatch.setattr(hook, 'tee', lambda *_: None)
    monkeypatch.setattr(os, 'rename', count_hits)
    monkeypatch.setattr(os, 'setxattr', always_raise(OSError))
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'Popen', fake_subprocess)
    monkeypatch.setattr(sys, 'argv', ['python', 'P', 'e', 'u', 'g', 's', '1', 'c', 'h', 'f', 'E'])

    assert hook.run()

    assert count_hits.hits == 1


def test_no_collect(monkeypatch):
    attempt = 0

    def fake_subprocess(*args, **kwargs):
        nonlocal attempt
        ret = subprocess.CompletedProcess(args[0], 0)
        ret.stdin = io.BytesIO()
        assert attempt < 1
        if attempt == 0:
            assert args[0] == ['/usr/lib/systemd/systemd-coredump', 'P', 'u', 'g', 's', '1', 'c', 'h']
        attempt += 1
        return ret

    monkeypatch.setattr(hook, 'tee', lambda *_: None)
    monkeypatch.setattr(os, 'rename', lambda *_: None)
    monkeypatch.setattr(os, 'setxattr', unreachable)
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'Popen', fake_subprocess)
    monkeypatch.setattr(sys, 'argv', ['python', 'P', 'e', 'u', 'g', 's', '1', 'c', 'h', 'f', '/home/deck/.local/share/Steam/ubuntu12_64/cef.so'])

    assert not hook.run()
