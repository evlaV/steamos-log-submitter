# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import collections
import os
import pytest
import threading
import time
import steamos_log_submitter as sls
import steamos_log_submitter.helpers as helpers
from steamos_log_submitter.runner import submit
from . import awaitable, setup_categories, unreachable
from . import helper_directory, patch_module, count_hits  # NOQA: F401
from . import mock_config as testconf  # NOQA: F401


@pytest.fixture
def online(monkeypatch):
    monkeypatch.setattr(sls.util, 'check_network', lambda: True)


def setup_logs(helper_directory, logs):
    for fname, text in logs.items():
        with open(f'{sls.pending}/{fname}', 'w') as f:
            if text:
                f.write(text)


@pytest.mark.asyncio
async def test_offline(monkeypatch):
    monkeypatch.setattr(sls.util, 'check_network', lambda: False)
    monkeypatch.setattr(helpers, 'list_helpers', unreachable)
    await submit()


@pytest.mark.asyncio
async def test_disable_all(helper_directory, monkeypatch, online, patch_module, testconf):
    testconf.add_section('helpers.test')
    testconf.set('helpers.test', 'enable', 'off')

    setup_categories(['test'])

    patch_module.submit = unreachable
    await submit()


@pytest.mark.asyncio
async def test_disable_submit(helper_directory, monkeypatch, online, patch_module, testconf):
    testconf.add_section('helpers.test')
    testconf.set('helpers.test', 'submit', 'off')

    setup_categories(['test'])

    patch_module.submit = unreachable
    await submit()


@pytest.mark.asyncio
async def test_submit_no_categories(helper_directory, online):
    await submit()


@pytest.mark.asyncio
async def test_submit_empty(helper_directory, online, patch_module, count_hits):
    setup_categories(['test'])
    patch_module.submit = awaitable(count_hits)
    await submit()

    assert count_hits.hits == 0


@pytest.mark.asyncio
async def test_submit_skip_dot(helper_directory, online, patch_module, count_hits):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/.skip': ''})
    patch_module.submit = awaitable(count_hits)
    await submit()

    assert os.access(f'{sls.pending}/test/.skip', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/.skip', os.F_OK)
    assert not os.access(f'{sls.failed}/test/.skip', os.F_OK)
    assert count_hits.hits == 0


@pytest.mark.asyncio
async def test_missing_module(helper_directory, online):
    setup_categories(['foo'])
    setup_logs(helper_directory, {'foo/log': ''})
    await submit()

    assert os.access(f'{sls.pending}/foo/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/foo/log', os.F_OK)
    assert not os.access(f'{sls.failed}/foo/log', os.F_OK)


@pytest.mark.asyncio
async def test_broken_module(helper_directory, online):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': ''})
    await submit()

    assert os.access(f'{sls.pending}/test/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/log', os.F_OK)
    assert not os.access(f'{sls.failed}/test/log', os.F_OK)


@pytest.mark.asyncio
async def test_success(helper_directory, online, patch_module, count_hits):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': ''})
    count_hits.ret = helpers.HelperResult()

    patch_module.submit = awaitable(count_hits)
    await submit()

    assert not os.access(f'{sls.pending}/test/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/test/log', os.F_OK)
    assert not os.access(f'{sls.failed}/test/log', os.F_OK)
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_transient_failure(helper_directory, online, patch_module, count_hits):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': ''})
    count_hits.ret = helpers.HelperResult(helpers.HelperResult.TRANSIENT_ERROR)

    patch_module.submit = awaitable(count_hits)
    await submit()

    assert os.access(f'{sls.pending}/test/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/log', os.F_OK)
    assert not os.access(f'{sls.failed}/test/log', os.F_OK)
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_permanent_failure(helper_directory, online, patch_module, count_hits):
    setup_categories(['test'])
    setup_logs(helper_directory, collections.OrderedDict([('test/log', ''), ('test/log2', '')]))
    count_hits.ret = helpers.HelperResult(helpers.HelperResult.PERMANENT_ERROR)

    patch_module.submit = awaitable(count_hits)
    await submit()

    assert not os.access(f'{sls.pending}/test/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/log', os.F_OK)
    assert os.access(f'{sls.failed}/test/log', os.F_OK)
    assert not os.access(f'{sls.pending}/test/log2', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/log2', os.F_OK)
    assert os.access(f'{sls.failed}/test/log2', os.F_OK)
    assert count_hits.hits == 2


@pytest.mark.asyncio
async def test_class_failure(helper_directory, online, patch_module, count_hits):
    setup_categories(['test'])
    setup_logs(helper_directory, collections.OrderedDict([('test/log', ''), ('test/log2', '')]))
    count_hits.ret = helpers.HelperResult(helpers.HelperResult.CLASS_ERROR)

    patch_module.submit = awaitable(count_hits)
    await submit()

    assert os.access(f'{sls.pending}/test/log', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/log', os.F_OK)
    assert not os.access(f'{sls.failed}/test/log', os.F_OK)
    assert os.access(f'{sls.pending}/test/log2', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/log2', os.F_OK)
    assert not os.access(f'{sls.failed}/test/log2', os.F_OK)
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_filename(helper_directory, online, patch_module):
    setup_categories(['test'])
    setup_logs(helper_directory, collections.OrderedDict([('test/fail', ''), ('test/log', '')]))

    async def fake_submit(fname):
        if fname == f'{sls.pending}/test/log':
            return helpers.HelperResult()
        return helpers.HelperResult(helpers.HelperResult.PERMANENT_ERROR)

    patch_module.submit = fake_submit
    await submit()

    assert not os.access(f'{sls.pending}/test/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/test/log', os.F_OK)
    assert not os.access(f'{sls.failed}/test/log', os.F_OK)

    assert not os.access(f'{sls.pending}/test/fail', os.F_OK)
    assert not os.access(f'{sls.uploaded}/test/fail', os.F_OK)
    assert os.access(f'{sls.failed}/test/fail', os.F_OK)


def test_lock(helper_directory, online, patch_module):
    setup_categories(['test'])
    setup_logs(helper_directory, {'test/log': ''})

    async def fake_submit(fname):
        time.sleep(0.1)
        return helpers.HelperResult()

    patch_module.submit = fake_submit
    running = 0

    def run():
        nonlocal running
        if running != 0:
            time.sleep(0.05)
            assert os.access(f'{sls.pending}/test/.lock', os.F_OK)
        running += 1
        asyncio.run(submit())

    thread_a = threading.Thread(target=run)
    thread_b = threading.Thread(target=run)

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    assert not os.access(f'{sls.pending}/test/log', os.F_OK)
    assert os.access(f'{sls.uploaded}/test/log', os.F_OK)
    assert running == 2


@pytest.mark.asyncio
async def test_error_continue(helper_directory, monkeypatch, patch_module, count_hits):
    real_listdir = os.listdir

    def fail_count(*args, **kwargs):
        count_hits()
        if count_hits.hits == 2:
            raise FileNotFoundError
        return real_listdir(*args, **kwargs)

    setup_categories(['test', 'test2'])
    monkeypatch.setattr(os, 'listdir', fail_count)

    patch_module.submit = lambda _: True
    await submit()

    assert count_hits.hits == 3
