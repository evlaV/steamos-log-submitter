# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import socket
from typing import Any, Optional

import steamos_log_submitter.daemon as daemon

logger = logging.getLogger(__name__)


class ClientError(RuntimeError):
    def __init__(self, reply=None):
        super().__init__()
        self.reply = reply


class UnknownError(ClientError):
    pass


class InvalidCommandError(ClientError):
    pass


class InvalidDataError(ClientError):
    pass


class InvalidArgumentsError(ClientError):
    pass


exception_map = {
    daemon.Reply.UNKNOWN_ERROR: UnknownError,
    daemon.Reply.INVALID_COMMAND: InvalidCommandError,
    daemon.Reply.INVALID_DATA: InvalidDataError,
    daemon.Reply.INVALID_ARGUMENTS: InvalidArgumentsError,
}


class Client:
    def __init__(self, sock=None, *, path=None):
        if sock:
            self._socket = sock
        else:
            self._socket = socket.socket(family=socket.AF_UNIX)
            self._socket.connect(path or daemon.socket)

    def _transact(self, command: str, args: Optional[dict[str, Any]] = None) -> Any:
        command_obj = daemon.Command(command, args)
        self._socket.send(command_obj.serialize())
        reply = self._socket.recv(4096)
        reply = daemon.Reply.deserialize(reply)
        if reply.status == daemon.Reply.OK:
            return reply.data
        exc = exception_map[reply.status]
        raise exc(reply)

    def enable(self, state: bool = True):
        self._transact('enable', {'state': state})

    def disable(self):
        self.enable(False)

    def enable_helpers(self, helpers: list[str]):
        self.set_helpers_enabled({helper: True for helper in helpers})

    def disable_helpers(self, helpers: list[str]):
        self.set_helpers_enabled({helper: False for helper in helpers})

    def set_helpers_enabled(self, helpers: dict[str, bool]):
        self._transact('enable-helpers', {'helpers': helpers})

    def status(self) -> bool:
        reply = self._transact('status')
        return reply['enabled']

    def list(self) -> list[str]:
        return self._transact('list')

    def set_steam_info(self, key: str, value: Any):
        self._transact('set-steam-info', {'key': key, 'value': value})

    def shutdown(self):
        self._transact('shutdown')

    def trigger(self):
        self._transact('trigger')
