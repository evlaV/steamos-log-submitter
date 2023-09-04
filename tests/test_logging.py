# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import collections
import logging
import os
import pytest
import tempfile
import steamos_log_submitter as sls
import steamos_log_submitter.client
from . import count_hits, drop_root, mock_config  # NOQA: F401

logger = logging.getLogger(__name__)


def test_log_to_file():
    tmpdir = tempfile.TemporaryDirectory(prefix='sls-')
    sls.logging.reconfigure_logging(f'{tmpdir.name}/log')

    logger.error('foo')

    assert os.access(f'{tmpdir.name}/log', os.F_OK)
    with open(f'{tmpdir.name}/log') as f:
        log = f.read()

    assert log.strip().endswith('foo')
    assert 'ERROR' in log


def test_log_level(mock_config):
    tmpdir = tempfile.TemporaryDirectory(prefix='sls-')
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'critical')
    sls.logging.reconfigure_logging(f'{tmpdir.name}/log')

    logger.critical('foo')
    logger.error('foo')

    assert os.access(f'{tmpdir.name}/log', os.F_OK)
    with open(f'{tmpdir.name}/log') as f:
        log = f.read()

    assert 'CRITICAL' in log
    assert 'ERROR' not in log


def test_log_level_invalid(mock_config):
    tmpdir = tempfile.TemporaryDirectory(prefix='sls-')
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'fake')
    sls.logging.reconfigure_logging(f'{tmpdir.name}/log')

    logger.warning('foo')
    logger.info('foo')

    assert os.access(f'{tmpdir.name}/log', os.F_OK)
    with open(f'{tmpdir.name}/log') as f:
        log = f.read()

    assert 'WARNING' in log
    assert 'INFO' not in log


def test_log_level_invalid2(mock_config, monkeypatch):
    tmpdir = tempfile.TemporaryDirectory(prefix='sls-')
    logging.FAKE = 5
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'FAKE')
    sls.logging.reconfigure_logging(f'{tmpdir.name}/log')

    logger.warning('foo')
    logger.info('foo')

    del logging.FAKE
    assert os.access(f'{tmpdir.name}/log', os.F_OK)
    with open(f'{tmpdir.name}/log') as f:
        log = f.read()

    assert 'WARNING' in log
    assert 'INFO' not in log


def test_log_open_failure(capsys, drop_root):
    try:
        open('/nonexistent', 'w')
        pytest.skip('File is writable, are we running as root?')
        return
    except PermissionError:
        pass
    sls.logging.reconfigure_logging('/nonexistent')
    assert capsys.readouterr().err.strip().endswith("Couldn't open log file")


@pytest.mark.asyncio
async def test_remote(count_hits, monkeypatch):
    client = collections.namedtuple('client', ['log'])

    async def log(module, level, message, created):
        count_hits()
        assert module == 'steamos_log_submitter.test'
        assert level == logging.WARNING
        assert message == 'foo'

    def make_client():
        c = client(log)
        return c

    monkeypatch.setattr(sls.client, 'Client', make_client)
    sls.logging.reconfigure_logging(remote=True)

    try:
        logger = logging.getLogger('steamos_log_submitter.test')
        logger.warning('foo')
        await sls.logging.RemoteHandler.drain()
        assert count_hits.hits == 1
    finally:
        sls.logging.reconfigure_logging()
