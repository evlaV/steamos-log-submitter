# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
from steamos_log_submitter.config import get_config
from steamos_log_submitter.logging import reconfigure_logging
import steamos_log_submitter.exceptions as exceptions
import steamos_log_submitter.runner as runner
import steamos_log_submitter.steam as steam
import steamos_log_submitter.util as util

import asyncio

__all__ = [
    # Constants
    'base',
    'pending',
    'failed',
    'uploaded',
    # Utility functions
    'get_config',
    'get_data',
    'trigger',
    # Submodules
    'helpers',
    'exceptions',
    'steam',
    'util',
]

base_config = get_config(__name__, defaults={
    'enable': 'off',
    'base': '/var/lib/steamos-log-submitter',
})

base = base_config['base']
pending = f'{base}/pending'
uploaded = f'{base}/uploaded'
failed = f'{base}/failed'

reconfigure_logging()

# This needs to be imported late so that sls.base is populated
from steamos_log_submitter.data import get_data  # NOQA: E402

# This needs to be imported late so that sls.get_data is populated
import steamos_log_submitter.helpers as helpers  # NOQA: E402


def trigger():
    asyncio.run(runner.trigger())
