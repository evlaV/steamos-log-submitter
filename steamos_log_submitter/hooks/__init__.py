#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import steamos_log_submitter as sls
import steamos_log_submitter.client

logger = logging.getLogger(__name__)


def trigger() -> None:
    with sls.util.drop_root():
        try:
            sls.client.Client().trigger()
        except FileNotFoundError:
            logger.info('Cannot trigger submission as the daemon does not appear to be active')
