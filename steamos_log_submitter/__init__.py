# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
from steamos_log_submitter.config import get_config
from steamos_log_submitter.lockfile import LockHeldError
from steamos_log_submitter.logging import reconfigure_logging
import steamos_log_submitter.exceptions as exceptions
import steamos_log_submitter.helpers as helpers
import steamos_log_submitter.steam as steam
import steamos_log_submitter.util as util

import logging as _logging
import os

__all__ = [
    # Constants
    'base',
    'pending',
    'failed',
    'uploaded',
    # Utility functions
    'get_config',
    'get_data',
    'submit',
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

logger = _logging.getLogger(__name__)

# This needs to be imported late so that sls.base is populated
from steamos_log_submitter.data import get_data  # NOQA: E402


def trigger():
    if base_config['enable'] == 'on':
        logger.info('Routine collection/submission triggered')
        try:
            collect()
        except Exception as e:
            logger.critical('Unhandled exception while collecting logs', exc_info=e)
        try:
            submit()
        except Exception as e:
            logger.critical('Unhandled exception while submitting logs', exc_info=e)
    else:
        logger.debug('Routine collection/submission is disabled')


def collect():
    logger.info('Starting log collection')
    for category in helpers.list_helpers():
        cat_config = get_config(f'steamos_log_submitter.helpers.{category}')
        if cat_config.get('enable', 'on') != 'on' or cat_config.get('collect', 'on') != 'on':
            continue
        logger.info(f'Collecting logs for {category}')
        try:
            with helpers.lock(category):
                helper = helpers.create_helper(category)
                helper.collect()
        except LockHeldError:
            # Another process is currently working on this directory
            logger.warning(f'Lock already held trying to collect logs for {category}')
            continue
        except Exception as e:
            logger.error(f'Encountered error collecting logs for {category}', exc_info=e)
            continue
    logger.info('Finished log collection')


def submit():
    logger.info('Starting log submission')
    if not util.check_network():
        logger.info('Network is offline, bailing out')
        return

    for category in helpers.list_helpers():
        cat_config = get_config(f'steamos_log_submitter.helpers.{category}')
        if cat_config.get('enable', 'on') != 'on' or cat_config.get('submit', 'on') != 'on':
            continue
        logger.info(f'Submitting logs for {category}')
        try:
            logs = os.listdir(f'{pending}/{category}')
        except OSError as e:
            logger.error(f'Encountered error listing logs for {category}', exc_info=e)
            continue

        if not logs:
            logger.info('No logs found, skipping')
            continue

        try:
            with helpers.lock(category):
                try:
                    helper = helpers.create_helper(category)
                    for log in logs:
                        if log.startswith('.'):
                            continue
                        logger.debug(f'Found log {category}/{log}')
                        result = helper.submit(f'{pending}/{category}/{log}')
                        if result.code == helpers.HelperResult.OK:
                            logger.debug(f'Succeeded in submitting {category}/{log}')
                            os.replace(f'{pending}/{category}/{log}', f'{uploaded}/{category}/{log}')
                        else:
                            logger.warning(f'Failed to submit log {category}/{log} with code {result.code}')
                        if result.code == helpers.HelperResult.PERMANENT_ERROR:
                            os.replace(f'{pending}/{category}/{log}', f'{failed}/{category}/{log}')
                        elif result.code == helpers.HelperResult.CLASS_ERROR:
                            break
                except Exception as e:
                    logger.error(f'Encountered error submitting logs for {category}', exc_info=e)
                    continue
        except LockHeldError:
            # Another process is currently working on this directory
            logger.warning(f'Lock already held trying to submit logs for {category}')
            continue
    logger.info('Finished log submission')
