# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import pytest
import steamos_log_submitter as sls
from steamos_log_submitter.runner import collect
from . import awaitable, unreachable
from . import count_hits, helper_directory, mock_config, patch_module, setup_categories  # NOQA: F401


async def submit(log):
    return True


@pytest.mark.asyncio
async def test_disable_all(helper_directory, mock_config, monkeypatch, patch_module):
    patch_module.enable(False)
    setup_categories(['test'])

    patch_module.submit = unreachable
    patch_module.collect = unreachable
    await collect()


@pytest.mark.asyncio
async def test_disable_collect(helper_directory, mock_config, monkeypatch, patch_module):
    patch_module.enable_collect(False)
    setup_categories(['test'])

    patch_module.submit = unreachable
    patch_module.collect = unreachable
    await collect()


@pytest.mark.asyncio
async def test_disable_collect_global(helper_directory, mock_config, monkeypatch, patch_module):
    mock_config.add_section('sls')
    mock_config.set('sls', 'collect', 'off')
    setup_categories(['test'])

    patch_module.submit = unreachable
    patch_module.collect = unreachable
    await collect()


@pytest.mark.asyncio
async def test_module(helper_directory, monkeypatch, patch_module, count_hits):
    setup_categories(['test'])

    patch_module.submit = submit
    patch_module.collect = awaitable(count_hits)
    await collect()

    assert count_hits.hits


@pytest.mark.asyncio
async def test_lock(helper_directory, monkeypatch, patch_module, count_hits):
    setup_categories(['test'])

    patch_module.submit = submit
    patch_module.collect = awaitable(count_hits)

    lock = sls.lockfile.Lockfile(f'{sls.pending}/test/.lock')
    lock.lock()
    await collect()

    assert not count_hits.hits

    lock.unlock()
    await collect()

    assert count_hits.hits


@pytest.mark.asyncio
async def test_error_continue(helper_directory, monkeypatch, patch_module, count_hits):
    async def fail_count(*args, **kwargs):
        count_hits()
        assert count_hits.hits != 1
        return False

    setup_categories(['test', 'test2'])

    patch_module.submit = submit
    patch_module.collect = fail_count
    await collect()

    assert count_hits.hits == 2
