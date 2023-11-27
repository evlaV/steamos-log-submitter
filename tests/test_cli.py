# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import pytest
import steamos_log_submitter as sls
import steamos_log_submitter.cli as cli
import steamos_log_submitter.helpers as helpers
import steamos_log_submitter.runner as runner
from . import awaitable, setup_categories, setup_logs
from . import count_hits, drop_root, helper_directory, mock_config, open_shim, patch_module  # NOQA: F401
from .daemon import dbus_client, dbus_daemon  # NOQA: F401
from .dbus import real_dbus  # NOQA: F401


@pytest.fixture
async def cli_wrapper(dbus_client, monkeypatch):
    daemon, client = await dbus_client
    monkeypatch.setattr(cli.ClientWrapper, 'bus', client._bus)
    return daemon, client


@pytest.mark.asyncio
async def test_no_daemon(monkeypatch, real_dbus):
    bus = await real_dbus
    monkeypatch.setattr(cli.ClientWrapper, 'bus', bus)

    async with cli.ClientWrapper() as client:
        assert client is None


@pytest.mark.asyncio
async def test_no_daemon_message(monkeypatch, real_dbus, capsys):
    bus = await real_dbus
    monkeypatch.setattr(cli.ClientWrapper, 'bus', bus)
    await cli.amain(['status'])
    assert "Can't connect to daemon." in capsys.readouterr().err.strip()


@pytest.mark.asyncio
async def test_status(capsys, mock_config, cli_wrapper):
    daemon, client = await cli_wrapper

    mock_config.add_section('sls')
    mock_config.set('sls', 'enable', 'off')

    await cli.amain(['status'])
    assert capsys.readouterr().out.strip().endswith('disabled')

    mock_config.set('sls', 'enable', 'on')
    await cli.amain(['status'])
    assert capsys.readouterr().out.strip().endswith('enabled')

    mock_config.set('sls', 'enable', 'foo')
    await cli.amain(['status'])
    assert capsys.readouterr().out.strip().endswith('disabled')

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_status_helpers(capsys, mock_config, monkeypatch, patch_module, cli_wrapper):
    mock_config.add_section('helpers.test')
    daemon, client = await cli_wrapper

    await cli.amain(['status'])
    assert len(capsys.readouterr().out.strip().split('\n')) == 1

    await cli.amain(['status', '-a'])
    assert len(capsys.readouterr().out.strip().split('\n')) == 2

    await cli.amain(['status', 'test'])
    assert len(capsys.readouterr().out.strip().split('\n')) == 2

    await cli.amain(['status', 'test2'])
    outerr = capsys.readouterr()
    out = outerr.out.strip().split('\n')
    err = outerr.err.strip().split('\n')
    assert len(out) == 1
    assert len(err) == 1
    assert err[0] == 'Invalid helpers: test2'

    await cli.amain(['status', 'test', 'test2'])
    outerr = capsys.readouterr()
    out = outerr.out.strip().split('\n')
    err = outerr.err.strip().split('\n')
    assert len(out) == 2
    assert len(err) == 1
    assert err[0] == 'Invalid helpers: test2'

    mock_config.set('helpers.test', 'enable', 'off')
    await cli.amain(['status', '-a'])
    assert capsys.readouterr().out.strip().split('\n')[1].endswith('disabled')

    mock_config.set('helpers.test', 'enable', 'on')
    await cli.amain(['status', '-a'])
    assert capsys.readouterr().out.strip().split('\n')[1].endswith('enabled')

    mock_config.set('helpers.test', 'enable', 'off')
    await cli.amain(['status', 'test'])
    assert capsys.readouterr().out.strip().split('\n')[1].endswith('disabled')

    mock_config.set('helpers.test', 'enable', 'on')
    await cli.amain(['status', 'test'])
    assert capsys.readouterr().out.strip().split('\n')[1].endswith('enabled')

    mock_config.set('helpers.test', 'enable', 'on')
    await cli.amain(['status', 'test', 'test2'])
    assert capsys.readouterr().out.split('\n')[1].strip().endswith('enabled')

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_list(capsys, monkeypatch, cli_wrapper, patch_module):
    daemon, client = await cli_wrapper
    await cli.amain(['list'])
    assert capsys.readouterr().out.strip() == 'test'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_log_level(capsys, mock_config, monkeypatch, cli_wrapper):
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'ERROR')
    daemon, client = await cli_wrapper
    await cli.amain(['log-level'])
    assert capsys.readouterr().out.strip() == 'ERROR'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_set_log_level(mock_config, monkeypatch, cli_wrapper):
    mock_config.add_section('logging')
    daemon, client = await cli_wrapper
    await cli.amain(['log-level', 'error'])
    assert mock_config.get('logging', 'level') == 'ERROR'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_invalid_log_level(capsys, mock_config, monkeypatch, cli_wrapper):
    mock_config.add_section('logging')
    daemon, client = await cli_wrapper
    capsys.readouterr()
    await cli.amain(['log-level', 'foo'])
    assert capsys.readouterr().err.strip() == 'Please specify a valid log level'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_enable(cli_wrapper, mock_config):
    daemon, client = await cli_wrapper
    assert await client.status() is False

    await cli.amain(['enable'])
    assert await client.status() is True
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_disable(cli_wrapper, mock_config):
    daemon, client = await cli_wrapper
    await client.enable()
    assert await client.status() is True

    await cli.amain(['disable'])
    assert await client.status() is False
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_enable_helper(mock_config, monkeypatch, cli_wrapper, patch_module):
    daemon, client = await cli_wrapper
    await client.disable_helpers(['test'])
    assert mock_config.has_section('helpers.test')
    assert mock_config.get('helpers.test', 'enable') == 'off'

    await cli.amain(['enable-helper', 'test'])
    assert mock_config.get('helpers.test', 'enable') == 'on'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_disable_helper(mock_config, monkeypatch, cli_wrapper, patch_module):
    daemon, client = await cli_wrapper
    await client.enable_helpers(['test'])
    assert mock_config.has_section('helpers.test')
    assert mock_config.get('helpers.test', 'enable') == 'on'

    await cli.amain(['disable-helper', 'test'])
    assert mock_config.get('helpers.test', 'enable') == 'off'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_enable_helpers(mock_config, monkeypatch, cli_wrapper, patch_module):
    monkeypatch.setattr(helpers, 'list_helpers', lambda: ['test', 'test2'])
    daemon, client = await cli_wrapper
    await client.disable_helpers(['test', 'test2'])
    assert mock_config.has_section('helpers.test')
    assert mock_config.get('helpers.test', 'enable') == 'off'
    assert mock_config.has_section('helpers.test2')
    assert mock_config.get('helpers.test2', 'enable') == 'off'
    await cli.amain(['enable-helper', 'test', 'test2'])
    assert mock_config.get('helpers.test', 'enable') == 'on'
    assert mock_config.get('helpers.test2', 'enable') == 'on'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_enable_invalid_helper(capsys, mock_config, monkeypatch, cli_wrapper, patch_module):
    daemon, client = await cli_wrapper
    capsys.readouterr()
    await cli.amain(['enable-helper', 'test2'])
    assert not mock_config.has_section('helpers.test2')
    assert capsys.readouterr().err.strip() == 'Invalid helpers: test2'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_disable_helpers(mock_config, monkeypatch, cli_wrapper, patch_module):
    monkeypatch.setattr(helpers, 'list_helpers', lambda: ['test', 'test2'])
    daemon, client = await cli_wrapper
    await client.enable_helpers(['test', 'test2'])
    assert mock_config.has_section('helpers.test')
    assert mock_config.get('helpers.test', 'enable') == 'on'
    assert mock_config.has_section('helpers.test2')
    assert mock_config.get('helpers.test2', 'enable') == 'on'
    await cli.amain(['disable-helper', 'test', 'test2'])
    assert mock_config.get('helpers.test', 'enable') == 'off'
    assert mock_config.get('helpers.test2', 'enable') == 'off'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_list_pending(capsys, cli_wrapper, helper_directory, mock_config):
    setup_categories(['test', 'test2', 'test3'])
    setup_logs(helper_directory, {'test/a': '', 'test/b': '', 'test2/c': ''})
    daemon, client = await cli_wrapper

    await cli.amain(['pending'])
    assert capsys.readouterr().out.strip().split('\n') == ['test/a', 'test/b', 'test2/c']

    await cli.amain(['pending', 'test'])
    assert capsys.readouterr().out.strip().split('\n') == ['test/a', 'test/b']

    await cli.amain(['pending', 'test2'])
    assert capsys.readouterr().out.strip().split('\n') == ['test2/c']

    await cli.amain(['pending', 'test3'])
    assert capsys.readouterr().out.strip() == ''

    await cli.amain(['pending', 'test', 'test2'])
    assert capsys.readouterr().out.strip().split('\n') == ['test/a', 'test/b', 'test2/c']

    await cli.amain(['pending', 'test4'])
    outerr = capsys.readouterr()
    assert outerr.out.strip() == ''
    assert 'test4' in outerr.err.strip()

    await cli.amain(['pending', 'test', 'test4'])
    outerr = capsys.readouterr()
    assert outerr.out.strip().split('\n') == ['test/a', 'test/b']
    assert 'test4' in outerr.err.strip()

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_list_uploaded(capsys, cli_wrapper, helper_directory, mock_config):
    setup_categories(['test', 'test2', 'test3'])
    for fname in ('test/a', 'test/b', 'test2/c'):
        with open(f'{sls.uploaded}/{fname}', 'w'):
            pass
    daemon, client = await cli_wrapper

    await cli.amain(['uploaded'])
    assert capsys.readouterr().out.strip().split('\n') == ['test/a', 'test/b', 'test2/c']

    await cli.amain(['uploaded', 'test'])
    assert capsys.readouterr().out.strip().split('\n') == ['test/a', 'test/b']

    await cli.amain(['uploaded', 'test2'])
    assert capsys.readouterr().out.strip().split('\n') == ['test2/c']

    await cli.amain(['uploaded', 'test3'])
    assert capsys.readouterr().out.strip() == ''

    await cli.amain(['uploaded', 'test', 'test2'])
    assert capsys.readouterr().out.strip().split('\n') == ['test/a', 'test/b', 'test2/c']

    await cli.amain(['uploaded', 'test4'])
    outerr = capsys.readouterr()
    assert outerr.out.strip() == ''
    assert 'test4' in outerr.err.strip()

    await cli.amain(['uploaded', 'test', 'test4'])
    outerr = capsys.readouterr()
    assert outerr.out.strip().split('\n') == ['test/a', 'test/b']
    assert 'test4' in outerr.err.strip()

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_list_failed(capsys, cli_wrapper, helper_directory, mock_config):
    setup_categories(['test', 'test2', 'test3'])
    for fname in ('test/a', 'test/b', 'test2/c'):
        with open(f'{sls.failed}/{fname}', 'w'):
            pass
    daemon, client = await cli_wrapper

    await cli.amain(['failed'])
    assert capsys.readouterr().out.strip().split('\n') == ['test/a', 'test/b', 'test2/c']

    await cli.amain(['failed', 'test'])
    assert capsys.readouterr().out.strip().split('\n') == ['test/a', 'test/b']

    await cli.amain(['failed', 'test2'])
    assert capsys.readouterr().out.strip().split('\n') == ['test2/c']

    await cli.amain(['failed', 'test3'])
    assert capsys.readouterr().out.strip() == ''

    await cli.amain(['failed', 'test', 'test2'])
    assert capsys.readouterr().out.strip().split('\n') == ['test/a', 'test/b', 'test2/c']

    await cli.amain(['failed', 'test4'])
    outerr = capsys.readouterr()
    assert outerr.out.strip() == ''
    assert 'test4' in outerr.err.strip()

    await cli.amain(['failed', 'test', 'test4'])
    outerr = capsys.readouterr()
    assert outerr.out.strip().split('\n') == ['test/a', 'test/b']
    assert 'test4' in outerr.err.strip()

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_trigger(count_hits, monkeypatch, cli_wrapper, mock_config):
    count_hits.ret = [], []
    monkeypatch.setattr(runner, 'trigger', awaitable(count_hits))
    daemon, client = await cli_wrapper
    await cli.amain(['enable'])
    await cli.amain(['trigger'])
    await asyncio.sleep(0.01)
    assert count_hits.hits == 1
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_trigger_wait(count_hits, monkeypatch, cli_wrapper, mock_config):
    daemon, client = await cli_wrapper
    await cli.amain(['enable'])

    async def trigger():
        await asyncio.sleep(0.04)
        count_hits()
        return [], []

    monkeypatch.setattr(runner, 'trigger', trigger)

    await cli.amain(['trigger'])
    assert count_hits.hits == 0
    await asyncio.sleep(0.05)
    assert count_hits.hits == 1

    await cli.amain(['trigger', '--wait'])
    assert count_hits.hits == 2
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_trigger_wait2(count_hits, monkeypatch, cli_wrapper, mock_config):
    daemon, client = await cli_wrapper
    await cli.amain(['enable'])

    async def trigger():
        await asyncio.sleep(0.04)
        count_hits()
        return [], []

    monkeypatch.setattr(runner, 'trigger', trigger)

    await cli.amain(['trigger', '--wait'])
    assert count_hits.hits == 1

    await cli.amain(['trigger'])
    assert count_hits.hits == 1
    await asyncio.sleep(0.05)
    assert count_hits.hits == 2
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_logging(cli_wrapper, count_hits, mock_config, monkeypatch):
    daemon, client = await cli_wrapper
    expected_level = 'WARNING'

    def expect_level(level=None):
        nonlocal expected_level
        count_hits()
        assert level == expected_level

    monkeypatch.setattr(sls.logging, 'reconfigure_logging', expect_level)

    await cli.amain(['status'])
    assert not mock_config.has_section('steam')

    assert count_hits.hits == 1

    expected_level = 'DEBUG'

    await cli.amain(['--debug', 'status'])
    assert not mock_config.has_section('steam')

    assert count_hits.hits == 2

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_version(capsys, cli_wrapper, mock_config):
    daemon, client = await cli_wrapper

    await cli.amain(['version'])

    assert capsys.readouterr().out.strip() == f'Client {sls.__version__}\nDaemon {sls.__version__}'
    await daemon.shutdown()
