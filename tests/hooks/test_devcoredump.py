#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import io
import json
import os
import posix
import pytest
import sys
import tempfile
import time
import zipfile

import steamos_log_submitter as sls
import steamos_log_submitter.hooks.devcoredump as hook

from .. import BytesIO


@pytest.fixture
def staging_file(monkeypatch):
    blob = BytesIO()

    def fn(category: str, name: str, mode: str) -> io.BytesIO:
        blob.name = None
        return blob

    monkeypatch.setattr(sls.helpers, 'StagingFile', fn)
    return blob


@pytest.fixture
def dump_dir():
    d = tempfile.TemporaryDirectory(prefix='sls-')

    with open(f'{d.name}/data', 'w'):
        pass

    os.mkdir(f'{d.name}/workdir')
    os.symlink('workdir', f'{d.name}/failing_device')
    os.symlink('../../amspec', f'{d.name}/workdir/driver')

    yield d.name

    del d


@pytest.mark.asyncio
async def test_basic(dump_dir, monkeypatch, staging_file):
    monkeypatch.setattr(time, 'time_ns', lambda: 123456789)
    monkeypatch.setattr(os, 'uname', lambda: posix.uname_result(('1', '2', '3', '4', '5')))
    monkeypatch.setattr(sls.util, 'get_steamos_branch', lambda: 'main')
    monkeypatch.setattr(sys, 'argv', ['python', dump_dir])

    with open(f'{dump_dir}/data', 'wb') as f:
        f.write(b'\x7FELF')
    await hook.run()

    zf = zipfile.ZipFile(staging_file)
    with zf.open('metadata.json') as zff:
        metadata = json.loads(zff.read().decode())

    assert int(metadata['timestamp'] * 1_000_000_000) == 123456789
    assert metadata['kernel'] == '3'
    assert metadata['branch'] == 'main'

    with zf.open('dump') as zff:
        assert zff.read() == b'\x7FELF'
