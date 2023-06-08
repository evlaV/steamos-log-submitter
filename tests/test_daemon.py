# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import os
import pytest
import time
import steamos_log_submitter as sls
import steamos_log_submitter.helpers
import steamos_log_submitter.daemon

pytest_plugins = ('pytest_asyncio',)


async def transact(command: sls.daemon.Command, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    writer.write(command.serialize())
    await writer.drain()

    reply = await reader.readline()
    assert reply
    return sls.daemon.Reply.deserialize(reply)


@pytest.fixture
def fake_socket(monkeypatch):
    prefix = int((time.time() % 1) * 0x400000)
    fakesocket = f'{prefix:06x}.socket'
    monkeypatch.setattr(sls.daemon.Daemon, 'socket', fakesocket)
    yield fakesocket

    if os.access(fakesocket, os.F_OK):
        os.unlink(fakesocket)


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
async def test_invalid_format(test_daemon):
    daemon, reader, writer = await test_daemon
    writer.write(b'bad\n')
    await writer.drain()

    reply = await reader.readline()
    assert reply
    return sls.daemon.Reply.deserialize(reply)
    assert reply.status == sls.daemon.Reply.INVALID_DATA
    await daemon.shutdown()


@pytest.mark.asyncio
async def test_invalid_json(test_daemon):
    daemon, reader, writer = await test_daemon
    writer.write(b'{}\n')
    await writer.drain()

    reply = await reader.readline()
    assert reply
    return sls.daemon.Reply.deserialize(reply)
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
    async def raise_now():
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
