# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import logging
import os
from steamos_log_submitter.helpers import list_helpers

logger = logging.getLogger(__name__)


class Daemon:
    socket = 'steamos-log-submitter.socket'

    def __init__(self, *, exit_on_shutdown=False):
        self._conns = []
        self._exit_on_shutdown = exit_on_shutdown

    async def _conn_cb(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._conns.append((reader, writer))

        while self._serving:
            try:
                line = await reader.readline()
                if not line:
                    break
                command = line.decode(errors='replace').strip().split('\t')
                function = self._commands.get(command[0])
                logger.info(f'Remote command {command[0]} called')
                logger.debug(f'Arguments {command[1:]}')
                if not function:
                    logger.warning(f'Unknown command {command[0]} called')
                else:
                    try:
                        await function(self, *command[1:])
                    except Exception as e:
                        logger.error('Exception hit when attempting to run command', exc_info=e)

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

    async def _list(self):
        print(*list_helpers())

    _commands = {
        'shutdown': shutdown,
        'list': _list,
    }


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
