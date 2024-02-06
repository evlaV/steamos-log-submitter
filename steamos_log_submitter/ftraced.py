# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import importlib.machinery
import io
import logging
import os
import shutil
from typing import Optional, Self

import steamos_log_submitter as sls
import steamos_log_submitter.logging
from steamos_log_submitter.constants import DBUS_NAME, DBUS_ROOT
from steamos_log_submitter.types import DBusEncodable

__loader__: importlib.machinery.SourceFileLoader
logger = logging.getLogger(__loader__.name)

sls.logging.reconfigure_logging(sls.logging.config.get('path'))


class FtraceDaemon:
    BASE = '/sys/kernel/tracing/instances/steamos-log-submitter'

    def __init__(self: Self):
        self.server: Optional[asyncio.Server] = None
        self.pipe: Optional[io.BufferedReader] = None
        self._tasks: list[asyncio.Task] = []

    async def _got_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        command = await reader.readline()
        if command == b'shutdown\n' and self.server:
            writer.close()
            self.server.close()

    async def _send_event(self, trace: list[bytes], data: dict[str, DBusEncodable]) -> None:
        iface = await self.trace_obj.interface(f'{DBUS_NAME}.Trace')
        await iface.log_event([e.decode(errors='replace') for e in trace], {k: sls.dbus.to_variant(v) for k, v in data.items()})

    def _pipe_event(self) -> None:
        assert self.pipe
        entry = self.pipe.readline().split()
        data: dict[str, DBusEncodable] = {}
        if entry[-1].startswith(b'pid='):
            # Grab process info before it dies in the case of an OOM event
            pid = int(entry[-1].split(b'=')[1])
            appid = sls.util.get_appid(pid)
            comm, _ = sls.util.get_pid_stat(pid)
            data['pid'] = pid
            if appid is not None:
                data['appid'] = appid
            if comm is not None:
                data['comm'] = comm
        self._tasks.append(asyncio.create_task(self._send_event(entry, data)))

    async def open(self) -> None:
        os.makedirs(self.BASE, exist_ok=True)
        with open(f'{self.BASE}/events/oom/mark_victim/enable', 'w') as f:
            f.write('1')
        with open(f'{self.BASE}/set_ftrace_filter', 'w') as f:
            f.write('split_lock_warn')
        with open(f'{self.BASE}/current_tracer', 'w') as f:
            f.write('function')

        self.pipe = open(f'{self.BASE}/trace_pipe', 'rb')
        asyncio.get_event_loop().add_reader(self.pipe, self._pipe_event)
        self.server = await asyncio.start_unix_server(self._got_client, f'{sls.base}/ftraced.sock')
        shutil.chown(f'{sls.base}/ftraced.sock', 'steamos-log-submitter')
        await self.server.start_serving()

        self.trace_obj = sls.dbus.DBusObject(DBUS_NAME, f'{DBUS_ROOT}/helpers/Trace')

    async def close(self) -> None:
        if self.pipe is not None:
            try:
                self.pipe.close()
                self.pipe = None
            except OSError as e:
                logger.warn(f'Failed to close pipe: {e}')
        if self.server is not None:
            try:
                self.server.close()
                self.server = None
            except OSError as e:
                logger.warn(f'Failed to shutdown socket: {e}')
            try:
                os.unlink(f'{sls.base}/ftraced.sock')
            except OSError as e:
                logger.error(f'Failed to remove ftraced.sock: {e}')
        try:
            os.rmdir(self.BASE)
        except OSError as e:
            logger.error(f'Failed to remove trace directory: {e}')

    async def run(self) -> None:
        try:
            await self.open()
            assert self.server
            await self.server.serve_forever()
        finally:
            await self.close()


if __name__ == '__main__':
    daemon = FtraceDaemon()
    asyncio.run(daemon.run())
