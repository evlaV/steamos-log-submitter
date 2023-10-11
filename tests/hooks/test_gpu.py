#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import io
import json
import os
import posix
import pytest
import shutil
import subprocess
import time

import steamos_log_submitter as sls
import steamos_log_submitter.hooks.gpu as hook

from .. import always_raise, StringIO


@pytest.fixture
def staging_file(monkeypatch):
    blob = StringIO()

    def fn(category: str, name: str, mode: str) -> io.StringIO:
        blob.name = None
        return blob

    monkeypatch.setattr(sls.helpers, 'StagingFile', fn)
    return blob


@pytest.fixture
def fake_mesa(monkeypatch):
    def fn(*args, **kwargs) -> subprocess.CompletedProcess:
        ret: subprocess.CompletedProcess = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = 'mesa 23.2.34-1\n'
        return ret

    monkeypatch.setattr(subprocess, 'run', fn)


def test_basic(monkeypatch, fake_mesa) -> None:
    blob = StringIO()

    def staging_file(category: str, name: str, mode: str) -> io.StringIO:
        blob.name = None
        assert category == 'gpu'
        assert name == '123456789.json'
        return blob

    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456', 'NAME': 'hl2'})
    monkeypatch.setattr(os, 'uname', lambda: posix.uname_result(('1', '2', '3', '4', '5')))
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.helpers, 'StagingFile', staging_file)

    hook.run()

    blob.seek(0)
    value = json.load(blob)

    assert value['appid'] == 789
    assert value['branch'] == 'main'
    assert value['env']['ABC'] == '123'
    assert value['env']['NAME'] == 'hl2'
    assert value['executable'] == 'hl2.exe'
    assert value['comm'] == 'hl2'
    assert value['kernel'] == '3'
    assert value['mesa'] == '23.2.34-1'
    assert value['pid'] == 456
    assert value['timestamp'] == 0.123456789


def test_invalid_pid(monkeypatch, fake_mesa, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': 'foo'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)

    hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert value['env']['PID'] == 'foo'
    assert 'pid' not in value


def test_invalid_appid(monkeypatch, fake_mesa, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: None)

    hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert 'appid' not in value


def test_invalid_exe(monkeypatch, fake_mesa, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456'})
    monkeypatch.setattr(os, 'readlink', always_raise(FileNotFoundError))
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)

    hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert 'executable' not in value


def test_invalid_mesa(monkeypatch, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', always_raise(subprocess.SubprocessError))
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)

    hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert 'mesa' not in value
