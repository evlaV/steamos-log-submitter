# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import pwd
import pytest
import steamos_log_submitter.cli as cli
import steamos_log_submitter.helpers as helpers
import steamos_log_submitter.runner as runner
import steamos_log_submitter.steam as steam
from . import always_raise, awaitable
from . import count_hits, drop_root, mock_config, patch_module  # NOQA: F401
from .daemon import dbus_client, dbus_daemon, fake_socket  # NOQA: F401
from .dbus import real_dbus  # NOQA: F401


@pytest.fixture
async def cli_wrapper(dbus_client, monkeypatch):
    daemon, client = await dbus_client
    monkeypatch.setattr(cli.ClientWrapper, 'bus', client._bus)
    return daemon, client


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


@pytest.mark.asyncio
async def test_set_steam_key_account_name(mock_config, monkeypatch, cli_wrapper):
    monkeypatch.setattr(pwd, 'getpwuid', always_raise(OSError))
    daemon, client = await cli_wrapper
    await cli.amain(['set-steam-info', 'account-name', 'gaben'])
    assert mock_config.has_section('steam')
    assert mock_config.get('steam', 'account_name') == 'gaben'
    assert steam.get_steam_account_name() == 'gaben'


@pytest.mark.asyncio
async def test_set_steam_key_account_id(mock_config, monkeypatch, cli_wrapper):
    monkeypatch.setattr(pwd, 'getpwuid', always_raise(OSError))
    daemon, client = await cli_wrapper
    await cli.amain(['set-steam-info', 'account-id', '42'])
    assert mock_config.has_section('steam')
    assert mock_config.get('steam', 'account_id') == '42'
    assert steam.get_steam_account_id() == 42


@pytest.mark.asyncio
async def test_set_steam_key_account_id_invalid(mock_config, monkeypatch, cli_wrapper):
    monkeypatch.setattr(pwd, 'getpwuid', always_raise(OSError))
    daemon, client = await cli_wrapper
    assert not mock_config.has_section('steam')
    await cli.amain(['set-steam-info', 'account-id', 'gaben'])
    assert not mock_config.has_section('steam')
    assert steam.get_steam_account_id() is None


@pytest.mark.asyncio
async def test_set_steam_key_deck_serial(mock_config, monkeypatch, cli_wrapper):
    monkeypatch.setattr(pwd, 'getpwuid', always_raise(OSError))
    daemon, client = await cli_wrapper
    await cli.amain(['set-steam-info', 'deck-serial', 'AAAA0000'])
    assert mock_config.has_section('steam')
    assert mock_config.get('steam', 'deck_serial') == 'AAAA0000'
    assert steam.get_deck_serial() == 'AAAA0000'


@pytest.mark.asyncio
async def test_set_steam_key_invalid(mock_config, cli_wrapper):
    daemon, client = await cli_wrapper
    assert not mock_config.has_section('steam')
    try:
        await cli.amain(['set-steam-info', 'malicious_key', 'Breen'])
        assert False
    except SystemExit:
        pass
    assert not mock_config.has_section('steam')


@pytest.mark.asyncio
async def test_trigger(count_hits, monkeypatch, cli_wrapper):
    monkeypatch.setattr(runner, 'trigger', awaitable(count_hits))
    daemon, client = await cli_wrapper
    await cli.amain(['trigger'])
    await asyncio.sleep(0.01)
    assert count_hits.hits == 1


@pytest.mark.asyncio
async def test_trigger_wait(count_hits, monkeypatch, cli_wrapper):
    daemon, client = await cli_wrapper

    async def trigger(wait):
        await asyncio.sleep(0.05)
        count_hits()

    monkeypatch.setattr(daemon, 'trigger', trigger)

    await cli.amain(['trigger', '--wait'])
    assert count_hits.hits == 1
    await cli.amain(['trigger'])
    assert count_hits.hits == 1
    await asyncio.sleep(0.06)
    assert count_hits.hits == 2
