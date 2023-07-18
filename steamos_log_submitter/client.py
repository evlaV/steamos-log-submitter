# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
from typing import Any, Optional

import steamos_log_submitter as sls
from steamos_log_submitter.daemon import Command, Reply

logger = logging.getLogger(__name__)


class ClientError(RuntimeError):
    pass


class UnknownError(ClientError):
    pass


class InvalidCommandError(ClientError):
    pass


class InvalidDataError(ClientError):
    pass


class InvalidArgumentsError(ClientError):
    pass


exception_map = {
    Reply.UNKNOWN_ERROR: UnknownError,
    Reply.INVALID_COMMAND: InvalidCommandError,
    Reply.INVALID_DATA: InvalidDataError,
    Reply.INVALID_ARGUMENTS: InvalidArgumentsError,
}


class Client:
    def _transact(self, command: str, args: Optional[dict[str, Any]] = None) -> Any:
        command_obj = Command(command, args)
        self._socket.write(command_obj.serialize())
        reply = Reply.deserialize(self._socket.readline())
        if reply.status == Reply.OK:
            return reply.data
        exc = exception_map[reply.status]
        raise exc(reply)

    def enable(self, state: bool = True):
        self._transact('enable', {'state': 'on' if state else 'off'})

    def disable(self):
        self.enable(False)

    def enable_helpers(self, helpers: list[str], state: bool = True):
        pass

    def disable_helpers(self, helpers: list[str]):
        self.enable_helpers(helpers, False)

    def status(self) -> bool:
        reply = self._transact('status')
        return reply.get('status') == 'on'

    def set_steam_info(self, key: str, value: Any):
        pass

    def shutdown(self):
        pass

    def trigger(self):
        pass
