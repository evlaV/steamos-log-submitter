#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import glob
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

from .. import always_raise, awaitable, StringIO
from .. import count_hits, open_shim  # NOQA: F401


@pytest.fixture
def staging_file(monkeypatch):
    blob = StringIO()

    def fn(category: str, name: str, mode: str) -> io.StringIO:
        blob.name = None
        return blob

    monkeypatch.setattr(sls.helpers, 'StagingFile', fn)
    return blob


@pytest.fixture
def fake_pacman(monkeypatch):
    def fn(*args, **kwargs) -> subprocess.CompletedProcess:
        ret: subprocess.CompletedProcess = subprocess.CompletedProcess(args[0], 0)
        if args[0][0] == 'pacman':
            if args[0][2] == 'mesa':
                ret.stdout = 'mesa 23.2.34-1\n'
            elif args[0][2] == 'vulkan-radeon':
                ret.stdout = 'vulkan-radeon 24.3.0_devel.197194.steamos_24.11.0-2.1\n'
        return ret

    monkeypatch.setattr(subprocess, 'run', fn)


@pytest.mark.asyncio
async def test_basic(monkeypatch, fake_pacman) -> None:
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
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: ([{'MESSAGE': 'amdgpu: a'}, {'MESSAGE': 'drm: b'}, {'MESSAGE': 'not'}], None)))
    monkeypatch.setattr(sls.helpers, 'StagingFile', staging_file)

    await hook.run()

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
    assert value['radv'] == '24.3.0_devel.197194.steamos_24.11.0-2.1'
    assert value['pid'] == 456
    assert value['timestamp'] == 0.123456789
    assert value['journal'] == ['amdgpu: a', 'drm: b']


@pytest.mark.asyncio
async def test_invalid_pid(monkeypatch, fake_pacman, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': 'foo'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))

    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert value['env']['PID'] == 'foo'
    assert 'pid' not in value


@pytest.mark.asyncio
async def test_invalid_appid(monkeypatch, fake_pacman, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: None)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))

    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert 'appid' not in value


@pytest.mark.asyncio
async def test_invalid_exe(monkeypatch, fake_pacman, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456'})
    monkeypatch.setattr(os, 'readlink', always_raise(FileNotFoundError))
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))

    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert 'executable' not in value


@pytest.mark.asyncio
async def test_invalid_pacman(monkeypatch, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', always_raise(subprocess.SubprocessError))
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))

    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert 'mesa' not in value
    assert 'radv' not in value


@pytest.mark.asyncio
async def test_proc_scan_nothing(monkeypatch, open_shim, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '0'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', always_raise(subprocess.SubprocessError))
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))
    monkeypatch.setattr(glob, 'glob', lambda _: ['/proc/345/comm'])

    open_shim('steam')
    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert 'appid' not in value


@pytest.mark.asyncio
async def test_proc_scan(monkeypatch, open_shim, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '0'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', always_raise(subprocess.SubprocessError))
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))
    monkeypatch.setattr(glob, 'glob', lambda _: ['/proc/345/comm'])

    open_shim('reaper')
    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert value['appid'] == 789


@pytest.mark.asyncio
async def test_proc_scan_disappearing(monkeypatch, open_shim, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '0'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', always_raise(subprocess.SubprocessError))
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))
    monkeypatch.setattr(glob, 'glob', lambda _: ['/proc/345/comm'])

    open_shim.enoent()
    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert 'appid' not in value


@pytest.mark.asyncio
async def test_proc_scan_second_reaper(monkeypatch, open_shim, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '0'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', always_raise(subprocess.SubprocessError))
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789 if pid == 346 else None)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))
    monkeypatch.setattr(glob, 'glob', lambda _: ['/proc/345/comm', '/proc/346/comm'])

    open_shim('reaper')
    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert value['appid'] == 789


@pytest.mark.asyncio
async def test_proc_scan_invalid(monkeypatch, open_shim, staging_file) -> None:
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '0'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', always_raise(subprocess.SubprocessError))
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (None, None)))
    monkeypatch.setattr(glob, 'glob', lambda _: ['/proc/self/comm'])

    open_shim('reaper')
    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert 'appid' not in value


@pytest.mark.asyncio
async def test_umr(count_hits, monkeypatch, open_shim, staging_file) -> None:
    def fn(*args, **kwargs) -> subprocess.CompletedProcess:
        if args[0][0] != 'umr':
            raise subprocess.SubprocessError
        ret: subprocess.CompletedProcess = subprocess.CompletedProcess(args[0], 0)
        count_hits()
        if count_hits.hits == 1:
            assert args[0] == ['umr', '--by-pci', '0000:04:00.0', '-O', 'bits,halt_waves', '-go', '0', '-wa', 'gfx_0.0.0', '-go', '1']
            ret.stdout = 'wave stdout'
            ret.stderr = 'wave stderr'
        elif count_hits.hits == 2:
            assert args[0] == ['umr', '--by-pci', '0000:04:00.0', '-RS', 'gfx_0.0.0']
            ret.stdout = 'ring stdout'
            ret.stderr = 'ring stderr'
        else:
            assert False
        return ret

    journal = [
        {'MESSAGE': '[drm:gfx_v10_0_priv_reg_irq [amdgpu]] *ERROR* Illegal register access in command stream'},
        {'MESSAGE': '[drm:amdgpu_job_timedout [amdgpu]] *ERROR* ring gfx_0.0.0 timeout, signaled seq=363661, emitted seq=363662'},
        {'MESSAGE': '[drm:amdgpu_job_timedout [amdgpu]] *ERROR* Process information: process amdgpu_test pid 5366 thread amdgpu_test pid 5366'},
        {'MESSAGE': 'amdgpu 0000:04:00.0: amdgpu: GPU reset begin!'},
        {'MESSAGE': 'amdgpu 0000:04:00.0: amdgpu: MODE2 reset'},
        {'MESSAGE': 'amdgpu 0000:04:00.0: amdgpu: GPU reset succeeded, trying to resume'},
    ]
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456', 'NAME': 'hl2', 'ID_PATH': 'pci-0000:04:00.0'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', fn)
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (journal, None)))
    monkeypatch.setattr(glob, 'glob', lambda _: [])

    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert value['umr'] == {
        'wave': {
            'stdout': 'wave stdout',
            'stderr': 'wave stderr',
        },
        'ring': {
            'stdout': 'ring stdout',
            'stderr': 'ring stderr',
        }
    }


@pytest.mark.asyncio
async def test_umr_no_stderr(count_hits, monkeypatch, open_shim, staging_file) -> None:
    def fn(*args, **kwargs) -> subprocess.CompletedProcess:
        if args[0][0] != 'umr':
            raise subprocess.SubprocessError
        ret: subprocess.CompletedProcess = subprocess.CompletedProcess(args[0], 0)
        count_hits()
        if count_hits.hits == 1:
            assert args[0] == ['umr', '--by-pci', '0000:04:00.0', '-O', 'bits,halt_waves', '-go', '0', '-wa', 'gfx_0.0.0', '-go', '1']
            ret.stdout = 'wave stdout'
            ret.stderr = ''
        elif count_hits.hits == 2:
            assert args[0] == ['umr', '--by-pci', '0000:04:00.0', '-RS', 'gfx_0.0.0']
            ret.stdout = 'ring stdout'
            ret.stderr = ''
        else:
            assert False
        return ret

    journal = [
        {'MESSAGE': '[drm:gfx_v10_0_priv_reg_irq [amdgpu]] *ERROR* Illegal register access in command stream'},
        {'MESSAGE': '[drm:amdgpu_job_timedout [amdgpu]] *ERROR* ring gfx_0.0.0 timeout, signaled seq=363661, emitted seq=363662'},
        {'MESSAGE': '[drm:amdgpu_job_timedout [amdgpu]] *ERROR* Process information: process amdgpu_test pid 5366 thread amdgpu_test pid 5366'},
        {'MESSAGE': 'amdgpu 0000:04:00.0: amdgpu: GPU reset begin!'},
        {'MESSAGE': 'amdgpu 0000:04:00.0: amdgpu: MODE2 reset'},
        {'MESSAGE': 'amdgpu 0000:04:00.0: amdgpu: GPU reset succeeded, trying to resume'},
    ]
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456', 'NAME': 'hl2', 'ID_PATH': 'pci-0000:04:00.0'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', fn)
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (journal, None)))
    monkeypatch.setattr(glob, 'glob', lambda _: [])

    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert value['umr'] == {
        'wave': {
            'stdout': 'wave stdout',
        },
        'ring': {
            'stdout': 'ring stdout',
        }
    }


@pytest.mark.asyncio
async def test_no_umr(count_hits, monkeypatch, open_shim, staging_file) -> None:
    def fn(*args, **kwargs) -> subprocess.CompletedProcess:
        if args[0][0] == 'umr':
            count_hits()
            if count_hits.hits == 1:
                assert args[0] == ['umr', '--by-pci', '0000:04:00.0', '-O', 'bits,halt_waves', '-go', '0', '-wa', 'gfx_0.0.0', '-go', '1']
            elif count_hits.hits == 2:
                assert args[0] == ['umr', '--by-pci', '0000:04:00.0', '-RS', 'gfx_0.0.0']
            else:
                assert False
        raise subprocess.SubprocessError

    journal = [
        {'MESSAGE': '[drm:gfx_v10_0_priv_reg_irq [amdgpu]] *ERROR* Illegal register access in command stream'},
        {'MESSAGE': '[drm:amdgpu_job_timedout [amdgpu]] *ERROR* ring gfx_0.0.0 timeout, signaled seq=363661, emitted seq=363662'},
        {'MESSAGE': '[drm:amdgpu_job_timedout [amdgpu]] *ERROR* Process information: process amdgpu_test pid 5366 thread amdgpu_test pid 5366'},
        {'MESSAGE': 'amdgpu 0000:04:00.0: amdgpu: GPU reset begin!'},
        {'MESSAGE': 'amdgpu 0000:04:00.0: amdgpu: MODE2 reset'},
        {'MESSAGE': 'amdgpu 0000:04:00.0: amdgpu: GPU reset succeeded, trying to resume'},
    ]
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'environ', {'ABC': '123', 'PID': '456', 'NAME': 'hl2', 'ID_PATH': 'pci-0000:04:00.0'})
    monkeypatch.setattr(os, 'readlink', lambda _: 'hl2.exe')
    monkeypatch.setattr(shutil, 'chown', lambda *args, **kwargs: None)
    monkeypatch.setattr(subprocess, 'run', fn)
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sls.util, 'get_appid', lambda pid: 789)
    monkeypatch.setattr(sls.util, 'read_journal', awaitable(lambda *args, **kwargs: (journal, None)))
    monkeypatch.setattr(glob, 'glob', lambda _: [])

    await hook.run()

    staging_file.seek(0)
    value = json.load(staging_file)

    assert 'umr' not in value
