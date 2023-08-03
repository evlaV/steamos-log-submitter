# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import os
import pytest
import time
import steamos_log_submitter as sls
import steamos_log_submitter.helpers
import steamos_log_submitter.daemon
import steamos_log_submitter.runner
import steamos_log_submitter.steam
from . import awaitable, setup_categories, CustomConfig
from . import count_hits, helper_directory, mock_config, patch_module  # NOQA: F401
from .daemon import fake_socket, systemd_object  # NOQA: F401
from .dbus import mock_dbus  # NOQA: F401

pytest_plugins = ('pytest_asyncio',)


async def transact(command: sls.daemon.Command, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    writer.write(command.serialize())
    await writer.drain()

    reply = await reader.readline()
    assert reply
    return sls.daemon.Reply.deserialize(reply)


@pytest.fixture
async def test_daemon(fake_socket):
    daemon = sls.daemon.Daemon()
    await daemon.start()
    reader, writer = await asyncio.open_unix_connection(path=fake_socket)
    return daemon, reader, writer


@pytest.mark.asyncio
async def test_startup(fake_socket):
    assert not os.access(fake_socket, os.F_OK)
    daemon = sls.daemon.Daemon()
    await daemon.start()
    assert os.access(fake_socket, os.F_OK)
    assert os.access(fake_socket, os.R_OK | os.W_OK)
    await daemon.shutdown()
    assert not os.access(fake_socket, os.F_OK)


@pytest.mark.asyncio
async def test_shutdown(fake_socket):
    assert not os.access(fake_socket, os.F_OK)
    daemon = sls.daemon.Daemon()
    await daemon.start()
    assert os.access(fake_socket, os.F_OK)
    assert os.access(fake_socket, os.R_OK | os.W_OK)

    reader, writer = await asyncio.open_unix_connection(path=fake_socket)

    writer.write(b'{"command":"shutdown"}\n')
    await writer.drain()

    reply = await reader.readline()
    assert reply
    reply = sls.daemon.Reply.deserialize(reply)
    assert reply.status == sls.daemon.Reply.OK
    assert not reply.data

    assert not os.access(fake_socket, os.F_OK)


@pytest.mark.asyncio
async def test_disconnect(test_daemon):
    daemon, reader, writer = await test_daemon

    await asyncio.sleep(0.01)
    assert len(daemon._conns) == 1

    writer.close()
    await writer.wait_closed()
    await asyncio.sleep(0.01)
    assert len(daemon._conns) == 0

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_invalid_format(test_daemon):
    daemon, reader, writer = await test_daemon
    writer.write(b'bad\n')
    await writer.drain()

    reply = await reader.readline()
    assert reply
    reply = sls.daemon.Reply.deserialize(reply)
    assert reply.status == sls.daemon.Reply.INVALID_DATA
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_invalid_json(test_daemon):
    daemon, reader, writer = await test_daemon
    writer.write(b'{}\n')
    await writer.drain()

    reply = await reader.readline()
    assert reply
    reply = sls.daemon.Reply.deserialize(reply)
    assert reply.status == sls.daemon.Reply.INVALID_DATA
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_invalid_command(test_daemon):
    daemon, reader, writer = await test_daemon
    reply = await transact(sls.daemon.Command("foo"), reader, writer)
    assert reply
    assert reply.status == sls.daemon.Reply.INVALID_COMMAND
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_broken_command(test_daemon, monkeypatch):
    async def raise_now(self):
        raise Exception

    daemon, reader, writer = await test_daemon
    monkeypatch.setitem(daemon._commands, 'raise', raise_now)
    reply = await transact(sls.daemon.Command("raise"), reader, writer)
    assert reply.status == sls.daemon.Reply.UNKNOWN_ERROR
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_list(test_daemon, monkeypatch):
    def list_helpers():
        return ['test']

    monkeypatch.setattr(sls.helpers, 'list_helpers', list_helpers)

    daemon, reader, writer = await test_daemon
    reply = await transact(sls.daemon.Command("list"), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data == ['test']
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_get_log_level(test_daemon, mock_config):
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'INFO')
    daemon, reader, writer = await test_daemon
    reply = await transact(sls.daemon.Command("log-level"), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data == {'level': 'INFO'}
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_set_log_level(test_daemon, mock_config):
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'INFO')
    daemon, reader, writer = await test_daemon
    reply = await transact(sls.daemon.Command("log-level", {"level": "WARNING"}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data == {'level': 'WARNING'}
    assert mock_config.get('logging', 'level') == 'WARNING'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_set_log_level_migrate(test_daemon, monkeypatch):
    custom_config = CustomConfig(monkeypatch)
    custom_config.user.add_section('logging')
    custom_config.user.set('logging', 'level', 'WARNING')
    custom_config.write()

    sls.config.reload_config()
    assert sls.config.local_config_path == custom_config.local_file.name
    assert sls.config.user_config_path == custom_config.user_file.name
    assert sls.config.config.has_section('logging')
    assert sls.config.config.get('logging', 'level') == 'WARNING'
    assert not sls.config.local_config.has_section('logging')

    daemon, reader, writer = await test_daemon
    reply = await transact(sls.daemon.Command("log-level", {"level": "WARNING"}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data == {'level': 'WARNING'}

    sls.config.reload_config()
    assert not sls.config.config.has_option('logging', 'level')
    assert sls.config.local_config.has_section('logging')
    assert sls.config.local_config.get('logging', 'level') == 'WARNING'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_status(test_daemon, mock_config):
    daemon, reader, writer = await test_daemon
    reply = await transact(sls.daemon.Command("status"), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data['enabled'] is False

    mock_config.add_section('sls')
    mock_config.set('sls', 'enable', 'on')
    reply = await transact(sls.daemon.Command("status"), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data['enabled'] is True

    mock_config.set('sls', 'enable', 'off')
    reply = await transact(sls.daemon.Command("status"), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data['enabled'] is False
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_helper_status(test_daemon, mock_config, monkeypatch, helper_directory):
    daemon, reader, writer = await test_daemon
    setup_categories(['test'])

    reply = await transact(sls.daemon.Command("helper-status"), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data == {"test": {"enabled": True, "collection": True, "submission": True}}

    reply = await transact(sls.daemon.Command("helper-status", {"helpers": ["test"]}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data == {"test": {"enabled": True, "collection": True, "submission": True}}

    reply = await transact(sls.daemon.Command("helper-status", {"helpers": ["test2"]}), reader, writer)
    assert reply.status == sls.daemon.Reply.INVALID_ARGUMENTS
    assert reply.data == {"invalid-helper": ["test2"]}

    reply = await transact(sls.daemon.Command("helper-status", {"helpers": ["test", "test2"]}), reader, writer)
    assert reply.status == sls.daemon.Reply.INVALID_ARGUMENTS
    assert reply.data == {"invalid-helper": ["test2"]}

    mock_config.add_section('helpers.test')
    mock_config.set('helpers.test', 'enable', 'off')

    reply = await transact(sls.daemon.Command("helper-status"), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data == {"test": {"enabled": False, "collection": True, "submission": True}}

    reply = await transact(sls.daemon.Command("helper-status", {"helpers": ["test"]}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert reply.data == {"test": {"enabled": False, "collection": True, "submission": True}}


@pytest.mark.asyncio
async def test_enable(test_daemon, mock_config):
    daemon, reader, writer = await test_daemon
    reply = await transact(sls.daemon.Command("enable", {"state": True}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK

    assert mock_config.has_section('sls')
    assert mock_config.get('sls', 'enable') == 'on'

    reply = await transact(sls.daemon.Command("enable", {"state": False}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK

    assert mock_config.get('sls', 'enable') == 'off'

    reply = await transact(sls.daemon.Command("enable", {"state": "on"}), reader, writer)
    assert reply.status == sls.daemon.Reply.INVALID_ARGUMENTS

    reply = await transact(sls.daemon.Command("enable"), reader, writer)
    assert reply.status == sls.daemon.Reply.INVALID_ARGUMENTS
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_enable_helpers(test_daemon, mock_config, monkeypatch):
    daemon, reader, writer = await test_daemon
    monkeypatch.setattr(sls.helpers, 'list_helpers', lambda: ['test'])

    reply = await transact(sls.daemon.Command("enable-helpers", {"helpers": {"test": True}}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK

    assert mock_config.has_section('helpers.test')
    assert mock_config.get('helpers.test', 'enable') == 'on'

    reply = await transact(sls.daemon.Command("enable-helpers", {"helpers": {"test2": True}}), reader, writer)
    assert reply.status == sls.daemon.Reply.INVALID_ARGUMENTS
    assert reply.data == {'invalid-helper': ['test2']}

    reply = await transact(sls.daemon.Command("enable-helpers", {"helpers": {"test": "off"}}), reader, writer)
    assert reply.status == sls.daemon.Reply.INVALID_ARGUMENTS
    assert reply.data == {'invalid-state': ['test', 'off']}
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_set_steam_info(test_daemon, mock_config):
    daemon, reader, writer = await test_daemon
    reply = await transact(sls.daemon.Command("set-steam-info"), reader, writer)
    assert reply.status == sls.daemon.Reply.INVALID_ARGUMENTS

    reply = await transact(sls.daemon.Command("set-steam-info", {"key": "invalid", "value": "foo"}), reader, writer)
    assert reply.status == sls.daemon.Reply.INVALID_ARGUMENTS
    assert reply.data == {"key": "invalid"}

    reply = await transact(sls.daemon.Command("set-steam-info", {"key": "account_name", "value": "gaben"}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert sls.steam.get_steam_account_name() == 'gaben'

    reply = await transact(sls.daemon.Command("set-steam-info", {"key": "account_id", "value": 12345}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert sls.steam.get_steam_account_id() == 12345

    reply = await transact(sls.daemon.Command("set-steam-info", {"key": "deck_serial", "value": "HEV Mark IV"}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert sls.steam.get_deck_serial() == 'HEV Mark IV'
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_periodic(fake_socket, monkeypatch, count_hits, mock_config):
    daemon = sls.daemon.Daemon()
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(daemon, '_startup', 0.05)
    monkeypatch.setattr(daemon, '_interval', 0.04)
    await daemon.start()

    start = time.time()
    assert count_hits.hits == 0
    await asyncio.sleep(0.06)
    assert mock_config.has_section('daemon')
    assert mock_config.has_option('daemon', 'last_trigger')
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) - start < 0.06

    await asyncio.sleep(0.09)
    assert count_hits.hits == 3
    assert float(mock_config.get('daemon', 'last_trigger')) - start > 0.13

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_periodic_after_startup(fake_socket, monkeypatch, count_hits, mock_config):
    daemon = sls.daemon.Daemon()
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(daemon, '_startup', 0.05)
    monkeypatch.setattr(daemon, '_interval', 0.04)

    mock_config.add_section('daemon')
    mock_config.set('daemon', 'last_trigger', str(time.time() + 0.03))
    await daemon.start()

    start = time.time()
    assert count_hits.hits == 0
    await asyncio.sleep(0.06)
    assert count_hits.hits == 0
    assert float(mock_config.get('daemon', 'last_trigger')) - start > 0.02

    await asyncio.sleep(0.03)
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) - start > 0.05

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_periodic_before_startup(fake_socket, monkeypatch, count_hits, mock_config):
    daemon = sls.daemon.Daemon()
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(daemon, '_startup', 0.02)
    monkeypatch.setattr(daemon, '_interval', 0.1)

    mock_config.add_section('daemon')
    mock_config.set('daemon', 'last_trigger', str(time.time() - 0.2))
    await daemon.start()

    start = time.time()
    assert count_hits.hits == 0
    await asyncio.sleep(0.03)
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) - start > 0

    await asyncio.sleep(0.06)
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) - start < 0.04

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_periodic_delay(fake_socket, monkeypatch, count_hits, mock_config):
    daemon = sls.daemon.Daemon()
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(daemon, '_startup', 0.05)
    monkeypatch.setattr(daemon, '_interval', 0.05)

    start = time.time()
    await daemon.start()

    assert count_hits.hits == 0
    await asyncio.sleep(0.06)
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) - start > 0.05

    await asyncio.sleep(0.03)
    await daemon.trigger(wait=True)
    assert count_hits.hits == 2
    end = float(mock_config.get('daemon', 'last_trigger'))
    assert end - start > 0.08
    assert end - start < 0.1

    await asyncio.sleep(0.03)
    assert count_hits.hits == 2
    assert float(mock_config.get('daemon', 'last_trigger')) == end

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_inhibit(test_daemon, monkeypatch, count_hits, mock_config):
    monkeypatch.setattr(sls.runner, 'trigger', awaitable(count_hits))
    monkeypatch.setattr(sls.daemon.Daemon, '_startup', 0.05)
    monkeypatch.setattr(sls.daemon.Daemon, '_interval', 0.04)
    daemon, reader, writer = await test_daemon

    start = time.time()
    assert count_hits.hits == 0
    await asyncio.sleep(0.06)
    assert mock_config.has_section('daemon')
    assert mock_config.has_option('daemon', 'last_trigger')
    assert count_hits.hits == 1
    assert float(mock_config.get('daemon', 'last_trigger')) - start < 0.06

    reply = await transact(sls.daemon.Command("inhibit", {"state": True}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert count_hits.hits == 1
    assert mock_config.has_option('sls', 'inhibit')
    assert mock_config.get('sls', 'inhibit') == 'on'

    await asyncio.sleep(0.09)
    assert count_hits.hits == 1

    reply = await transact(sls.daemon.Command("trigger"), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert count_hits.hits == 1

    reply = await transact(sls.daemon.Command("inhibit", {"state": False}), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert mock_config.has_option('sls', 'inhibit')
    assert mock_config.get('sls', 'inhibit') == 'off'
    await asyncio.sleep(0)
    assert count_hits.hits == 2

    reply = await transact(sls.daemon.Command("trigger"), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert count_hits.hits == 3

    await daemon.shutdown()


@pytest.mark.asyncio
async def test_trigger_called(test_daemon, monkeypatch, count_hits, mock_config):
    daemon, reader, writer = await test_daemon
    monkeypatch.setattr(sls.runner, 'collect', awaitable(count_hits))
    monkeypatch.setattr(sls.runner, 'submit', awaitable(count_hits))

    mock_config.add_section('sls')
    mock_config.set('sls', 'enable', 'on')

    reply = await transact(sls.daemon.Command("trigger"), reader, writer)
    assert reply.status == sls.daemon.Reply.OK
    assert count_hits.hits == 2
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_trigger_wait(test_daemon, monkeypatch, mock_config):
    async def trigger():
        await asyncio.sleep(0.1)

    daemon, reader, writer = await test_daemon
    monkeypatch.setattr(sls.runner, 'trigger', trigger)

    start = time.time()
    reply = await transact(sls.daemon.Command("trigger", {"wait": False}), reader, writer)
    end = time.time()
    assert reply.status == sls.daemon.Reply.OK
    assert end - start < 0.1

    start = time.time()
    reply = await transact(sls.daemon.Command("trigger", {"wait": True}), reader, writer)
    end = time.time()
    assert reply.status == sls.daemon.Reply.OK
    assert end - start >= 0.1
