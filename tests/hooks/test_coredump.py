#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import io
import os
import shutil
import subprocess
import sys
from typing import Any

import steamos_log_submitter as sls
import steamos_log_submitter.hooks.coredump as hook

from .. import always_raise, unreachable, Popen
from .. import count_hits  # NOQA: F401


def test_tee_basic() -> None:
    out = io.BytesIO(b'a' * 4095 + b'b' * 4097)
    in_a = Popen(stdin=io.BytesIO())
    in_b = Popen(stdin=io.BytesIO())

    assert in_a.stdin
    in_a.stdin.close = lambda: None
    assert in_b.stdin
    in_b.stdin.close = lambda: None

    hook.tee(out, (in_a, in_b))  # type: ignore[arg-type]

    assert in_a.stdin.getvalue() == out.getvalue()
    assert in_b.stdin.getvalue() == out.getvalue()


def test_tee_missing_stdin() -> None:
    out = io.BytesIO(b'a' * 4095 + b'b' * 4097)
    in_a = Popen()
    in_b = Popen(stdin=io.BytesIO())

    assert not in_a.stdin
    assert in_b.stdin
    in_b.stdin.close = lambda: None

    hook.tee(out, (in_a, in_b))  # type: ignore[arg-type]

    assert in_a.stdin is None
    assert in_b.stdin.getvalue() == out.getvalue()


def test_tee_broken_in() -> None:
    out = io.BytesIO(b'a' * 4095 + b'b' * 4097)
    in_a = Popen(stdin=io.BytesIO())
    in_b = Popen(stdin=io.BytesIO())

    assert in_a.stdin
    in_a.stdin.close = lambda: None
    in_a.stdin.write = always_raise(OSError)

    assert in_b.stdin
    in_b.stdin.close = lambda: None

    hook.tee(out, (in_a, in_b))  # type: ignore[arg-type]

    assert in_a.stdin.getvalue() == b''
    assert in_b.stdin.getvalue() == out.getvalue()


def test_tee_broken_close(count_hits) -> None:
    out = io.BytesIO(b'a' * 4095 + b'b' * 4097)
    in_a = Popen(stdin=io.BytesIO(), wait=count_hits)

    assert in_a.stdin
    in_a.stdin.close = always_raise(OSError)
    hook.tee(out, (in_a,))  # type: ignore[arg-type]

    assert in_a.stdin.getvalue() == out.getvalue()
    assert count_hits.hits == 1


def test_should_collect() -> None:
    assert hook.should_collect('/usr/bin/true')
    assert hook.should_collect('/usr/lib/Xorg')
    assert hook.should_collect('/tmp/virus')
    assert not hook.should_collect('/tmp/.mount_not_a_virus')
    assert hook.should_collect('/home/deck/.local/bin/ruby')
    assert not hook.should_collect('/home/deck/.local/share/Steam/ubuntu12_64/secret')
    assert not hook.should_collect('/app/bin/ikea')


def test_basic(monkeypatch) -> None:
    attempt = 0
    tmpfile = f'{sls.pending}/minidump/.staging-1-e-P-None.dmp'

    def fake_subprocess(*args: Any, **kwargs: Any) -> Popen:
        nonlocal attempt
        ret = Popen(stdin=io.BytesIO(), returncode=0)
        assert attempt < 2
        if attempt == 0:
            assert args[0] == ['/usr/lib/systemd/systemd-coredump', 'P', 'u', 'g', 's', '1', 'c', 'h']
        elif attempt == 1:
            assert args[0] == ['/usr/lib/breakpad/core_handler', 'P', tmpfile]
        attempt += 1
        return ret

    def setxattr(filename: str, name: str, value: bytes) -> None:
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


def test_broken_xattr(monkeypatch, count_hits) -> None:
    def fake_subprocess(*args: Any, **kwargs: Any) -> Popen:
        ret = Popen()
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


def test_no_collect(monkeypatch) -> None:
    attempt = 0

    def fake_subprocess(*args: Any, **kwargs: Any) -> Popen:
        nonlocal attempt
        ret = Popen()
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
