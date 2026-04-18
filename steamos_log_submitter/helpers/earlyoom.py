# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_fast as dbus
import json
import os
import time
from . import Helper, HelperResult

import steamos_log_submitter as sls
import steamos_log_submitter.dbus
from steamos_log_submitter.aggregators.sentry import SentryEvent
from steamos_log_submitter.types import JSONEncodable


class EarlyoomHelper(Helper):
    valid_extensions = frozenset({'.json'})

    @classmethod
    def handle_log(cls, msg: dbus.Message) -> None:
        ts = time.time_ns()
        log: dict[str, JSONEncodable] = {k: v.value for k, v in msg.body[0].items()}
        comm = log.get('comm')
        if comm:
            fname = f'{comm} {ts}.json'
        else:
            fname = f'{ts}.json'
        with open(f'{sls.pending}/{cls.name}/{fname}', 'w') as f:
            json.dump(log, f)

    @classmethod
    async def startup(cls) -> None:
        match_rule = sls.dbus.MatchRule("type='signal',interface='com.steampowered.HoloEarlyoom',path='/com/steampowered/HoloEarlyoom',member='ProcessKilled'")
        if not await sls.dbus.add_match_rule(match_rule, cls.handle_log):
            cls.logger.error('Failed to listen for earlyoom events')

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        basename = os.path.basename(fname)
        event = SentryEvent(cls.config['dsn'])
        try:
            with open(fname, 'rb') as f:
                log = f.read()
        except OSError as e:
            cls.logger.error(f'Failed to open log file {basename}: {e}')
            return HelperResult.TRANSIENT_ERROR
        try:
            parsed_log = json.loads(log)
        except json.decoder.JSONDecodeError as e:
            cls.logger.error(f'Earlyoom JSON {basename} failed to parse', exc_info=e)
            return HelperResult.PERMANENT_ERROR

        appid = parsed_log.get('steamappid')
        fingerprint = []
        tags = {}
        if 'uid' in parsed_log:
            tags['uid'] = parsed_log['uid']

        comm = parsed_log.get('comm')
        if comm is not None:
            tags['comm'] = comm
            fingerprint.append(f'comm:{comm}')

        if appid and comm:
            message = f'{comm} ({appid})'
        elif comm:
            message = comm
        elif appid:
            message = appid

        event.add_attachment({
            'mime-type': 'application/json',
            'filename': os.path.basename(fname),
            'data': log
        })
        event.appid = appid
        event.tags = tags
        event.fingerprint = fingerprint
        event.message = message
        return await event.send()
