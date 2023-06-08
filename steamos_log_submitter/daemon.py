# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import json
import logging
import os

import steamos_log_submitter as sls
from steamos_log_submitter.helpers import list_helpers

logger = logging.getLogger(__name__)


class Serializable:
    def serialize(self) -> str:
        data = {}
        for field in self._fields:
            field_data = getattr(self, field)
            if field_data is not None:
                data[field] = field_data

        return json.dumps(data)

    @classmethod
    def deserialize(cls, data):
        try:
            args = {}
            parsed_data = json.loads(data)
            for field in cls._fields:
                field_data = parsed_data.get(field)
                if field_data is not None:
                    args[field] = field_data
            return cls(**args)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning('Failed to deserialize command', exc_info=e)
            return None


class Command(Serializable):
    _fields = ['command', 'args']

    def __init__(self, command, args=None):
        self.command = command
        self.args = args or []


class Reply(Serializable):
    OK = 0
    UNKNOWN_ERROR = -1
    INVALID_COMMAND = -2
    INVALID_DATA = -3

    _fields = ['status', 'data']

    def __init__(self, status, data=None):
        self.status = status
        self.data = data


class Daemon:
    socket = 'steamos-log-submitter.socket'

    def __init__(self, *, exit_on_shutdown=False):
        self._conns = []
        self._exit_on_shutdown = exit_on_shutdown

    async def _run_command(self, command: dict) -> Reply:
        if not command:
            logger.warning('Got invalid command data')
            return Reply(status=Reply.INVALID_DATA)
        function = self._commands.get(command.command)
        logger.info(f'Remote command {command.command} called')
        logger.debug(f'Arguments {command.args}')
        if not function:
            logger.warning(f'Unknown command {command.command} called')
            return Reply(error=Reply.INVALID_COMMAND)
        try:
            reply = await function(self, *command.args)
            if type(reply) == Reply:
                return reply
            return Reply(Reply.OK, data=reply)
        except Exception as e:
            logger.error('Exception hit when attempting to run command', exc_info=e)
            return Reply(error=Reply.UNKNOWN_ERROR)

    async def _conn_cb(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._conns.append((reader, writer))

        while self._serving:
            try:
                line = await reader.readline()
                if not line:
                    break
                command = Command.deserialize(line.decode(errors='replace'))
                reply = await self._run_command(command)
                writer.write(reply.serialize().encode() + b'\n')

            except Exception as e:
                logger.error('Failed reading from remote connection', exc_info=e)
        self._conns.remove((reader, writer))

    async def start(self) -> None:
        if os.access(self.socket, os.F_OK):
            os.unlink(self.socket)

        self._serving = True
        self._server = await asyncio.start_unix_server(self._conn_cb, path=self.socket)
        os.chmod(self.socket, 0o660)

    async def shutdown(self):
        logger.info('Daemon shutting down')
        self._serving = False
        self._server.close()
        os.unlink(self.socket)

        if self._exit_on_shutdown:
            loop = asyncio.get_event_loop()
            loop.stop()

    async def trigger(self):
        sls.trigger()

    async def _list(self) -> Reply:
        helpers = list_helpers()
        return Reply(Reply.OK, data=helpers)

    _commands = {
        'shutdown': shutdown,
        'list': _list,
        'trigger': trigger,
    }


if __name__ == '__main__':
    daemon = Daemon(exit_on_shutdown=True)
    loop = asyncio.get_event_loop()
    loop.create_task(daemon.start())
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        if os.access(Daemon.socket, os.F_OK):
            os.unlink(Daemon.socket)
