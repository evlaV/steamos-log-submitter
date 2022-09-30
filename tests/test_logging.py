import configparser
import logging
import os
import tempfile
import steamos_log_submitter as sls
from . import mock_config

logger = logging.getLogger(__name__)


def test_log_to_file(mock_config):
    tmpdir = tempfile.TemporaryDirectory(prefix='sls-')
    mock_config.add_section('logging')
    mock_config.set('logging', 'path', f'{tmpdir.name}/log')
    sls.reconfigure_logging()

    logger.error('foo')

    assert os.access(f'{tmpdir.name}/log', os.F_OK)
    with open(f'{tmpdir.name}/log') as f:
        log = f.read()

    assert log.strip().endswith('foo')
    assert 'ERROR' in log


def test_log_level(mock_config):
    tmpdir = tempfile.TemporaryDirectory(prefix='sls-')
    mock_config.add_section('logging')
    mock_config.set('logging', 'path', f'{tmpdir.name}/log')
    mock_config.set('logging', 'level', 'critical')
    sls.reconfigure_logging()

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
    mock_config.set('logging', 'path', f'{tmpdir.name}/log')
    mock_config.set('logging', 'level', 'fake')
    sls.reconfigure_logging()

    logger.warning('foo')
    logger.info('foo')

    assert os.access(f'{tmpdir.name}/log', os.F_OK)
    with open(f'{tmpdir.name}/log') as f:
        log = f.read()

    assert 'WARNING' in log
    assert 'INFO' not in log

# vim:ts=4:sw=4:et
