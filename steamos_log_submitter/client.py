# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import socket
from typing import Any, Optional

import steamos_log_submitter.daemon as daemon
from steamos_log_submitter.types import JSON

logger = logging.getLogger(__name__)


class Client:
    def __init__(self, sock: Optional[socket.socket] = None, *, path: Optional[str] = None):
        if sock:
            self._socket = sock
        else:
            self._socket = socket.socket(family=socket.AF_UNIX)
            self._socket.connect(path or daemon.socket)

    def _transact(self, command: str, args: Optional[dict[str, Any]] = None) -> Any:
        command_obj = daemon.Command(command, args)
        self._socket.send(command_obj.serialize())
        reply_bytes = self._socket.recv(4096)
        reply = daemon.Reply.deserialize(reply_bytes)
        if not reply:
            raise daemon.UnknownError()
        if reply.status == daemon.Reply.OK:
            return reply.data
        exc = daemon.exception_map[reply.status]
        raise exc(reply.data)

    def enable(self, state: bool = True) -> None:
        self._transact('enable', {'state': state})

    def disable(self) -> None:
        self.enable(False)

    def enable_helpers(self, helpers: list[str]) -> None:
        self.set_helpers_enabled({helper: True for helper in helpers})

    def disable_helpers(self, helpers: list[str]) -> None:
        self.set_helpers_enabled({helper: False for helper in helpers})

    def set_helpers_enabled(self, helpers: dict[str, bool]) -> None:
        self._transact('enable-helpers', {'helpers': helpers})

    def status(self) -> bool:
        reply = self._transact('status')
        return reply['enabled']

    def helper_status(self, helpers: Optional[list[str]] = None) -> dict[str, dict[str, JSON]]:
        if helpers is None:
            reply = self._transact('helper-status')
        else:
            reply = self._transact('helper-status', {'helpers': helpers})
        return reply

    def list(self) -> list[str]:
        return self._transact('list')

    def log_level(self) -> str:
        return self._transact('log-level')['level']

    def set_log_level(self, level: str) -> None:
        self._transact('log-level', {'level': level})

    def set_steam_info(self, key: str, value: Any) -> None:
        self._transact('set-steam-info', {'key': key, 'value': value})

    def shutdown(self) -> None:
        self._transact('shutdown')

    def trigger(self, wait: bool = True) -> None:
        self._transact('trigger', {'wait': wait})
