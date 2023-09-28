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
import shutil
import subprocess
import time

import steamos_log_submitter as sls
import steamos_log_submitter.hooks.gpu as hook

from .. import always_raise


def test_basic(monkeypatch) -> None:
    blob = io.StringIO()

    def staging_file(category: str, name: str, mode: str) -> io.StringIO:
        blob.name = None
        blob.close = lambda: None
        assert category == 'gpu'
        assert name == '123456789.json'
        return blob

    def fake_subprocess(*args, **kwargs) -> subprocess.CompletedProcess:
        ret: subprocess.CompletedProcess = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = 'mesa 23.2.34-1\n'
        return ret

    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456', 'NAME': 'hl2'})
    monkeypatch.setattr(os, 'uname', lambda: posix.uname_result(('1', '2', '3', '4', '5')))
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', fake_subprocess)
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


def test_invalid_pid(monkeypatch) -> None:
    blob = io.StringIO()

    def staging_file(category: str, name: str, mode: str) -> io.StringIO:
        blob.name = None
        blob.close = lambda: None
        return blob

    def fake_subprocess(*args, **kwargs) -> subprocess.CompletedProcess:
        ret: subprocess.CompletedProcess = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = 'mesa 23.2.34-1\n'
        return ret

    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': 'foo'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', fake_subprocess)
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.helpers, 'StagingFile', staging_file)

    hook.run()

    blob.seek(0)
    value = json.load(blob)

    assert value['env']['PID'] == 'foo'
    assert 'pid' not in value


def test_invalid_appid(monkeypatch) -> None:
    blob = io.StringIO()

    def staging_file(category: str, name: str, mode: str) -> io.StringIO:
        blob.name = None
        blob.close = lambda: None
        return blob

    def fake_subprocess(*args, **kwargs) -> subprocess.CompletedProcess:
        ret: subprocess.CompletedProcess = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = 'mesa 23.2.34-1\n'
        return ret

    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', fake_subprocess)
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: None)
    monkeypatch.setattr(sls.helpers, 'StagingFile', staging_file)

    hook.run()

    blob.seek(0)
    value = json.load(blob)

    assert 'appid' not in value


def test_invalid_exe(monkeypatch) -> None:
    blob = io.StringIO()

    def staging_file(category: str, name: str, mode: str) -> io.StringIO:
        blob.name = None
        blob.close = lambda: None
        return blob

    def fake_subprocess(*args, **kwargs) -> subprocess.CompletedProcess:
        ret: subprocess.CompletedProcess = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = 'mesa 23.2.34-1\n'
        return ret

    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456'})
    monkeypatch.setattr(os, 'readlink', always_raise(FileNotFoundError))
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', fake_subprocess)
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.helpers, 'StagingFile', staging_file)

    hook.run()

    blob.seek(0)
    value = json.load(blob)

    assert 'executable' not in value


def test_invalid_mesa(monkeypatch) -> None:
    blob = io.StringIO()

    def staging_file(category: str, name: str, mode: str) -> io.StringIO:
        blob.name = None
        blob.close = lambda: None
        return blob

    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', always_raise(subprocess.SubprocessError))
    monkeypatch.setattr(sls.steam, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.helpers, 'StagingFile', staging_file)

    hook.run()

    blob.seek(0)
    value = json.load(blob)

    assert 'mesa' not in value
