#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import logging
import steamos_log_submitter as sls
import steamos_log_submitter.client

logger = logging.getLogger(__name__)


def trigger() -> None:
    try:
        asyncio.run(sls.client.Client().trigger(wait=False))
    except Exception as e:
        logger.warning("Couldn't trigger submission, exiting", exc_info=e)
