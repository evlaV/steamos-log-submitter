# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter as sls
from steamos_log_submitter.lockfile import LockHeldError

import logging
import os

logger = logging.getLogger(__name__)


async def collect():
    logger.info('Starting log collection')
    for category in sls.helpers.list_helpers():
        cat_config = sls.get_config(f'steamos_log_submitter.helpers.{category}')
        if cat_config.get('enable', 'on') != 'on' or cat_config.get('collect', 'on') != 'on':
            continue
        logger.info(f'Collecting logs for {category}')
        try:
            with sls.helpers.lock(category):
                helper = sls.helpers.create_helper(category)
                helper.collect()
        except LockHeldError:
            # Another process is currently working on this directory
            logger.warning(f'Lock already held trying to collect logs for {category}')
            continue
        except Exception as e:
            logger.error(f'Encountered error collecting logs for {category}', exc_info=e)
            continue
    logger.info('Finished log collection')


async def submit():
    logger.info('Starting log submission')
    if not sls.util.check_network():
        logger.info('Network is offline, bailing out')
        return

    for category in sls.helpers.list_helpers():
        cat_config = sls.get_config(f'steamos_log_submitter.helpers.{category}')
        if cat_config.get('enable', 'on') != 'on' or cat_config.get('submit', 'on') != 'on':
            continue
        logger.info(f'Submitting logs for {category}')
        try:
            logs = os.listdir(f'{sls.pending}/{category}')
        except OSError as e:
            logger.error(f'Encountered error listing logs for {category}', exc_info=e)
            continue

        if not logs:
            logger.info('No logs found, skipping')
            continue

        try:
            with sls.helpers.lock(category):
                try:
                    helper = sls.helpers.create_helper(category)
                    for log in logs:
                        if log.startswith('.'):
                            continue
                        logger.debug(f'Found log {category}/{log}')
                        result = helper.submit(f'{sls.pending}/{category}/{log}')
                        if result.code == sls.helpers.HelperResult.OK:
                            logger.debug(f'Succeeded in submitting {category}/{log}')
                            os.replace(f'{sls.pending}/{category}/{log}', f'{sls.uploaded}/{category}/{log}')
                        else:
                            logger.warning(f'Failed to submit log {category}/{log} with code {result.code}')
                        if result.code == sls.helpers.HelperResult.PERMANENT_ERROR:
                            os.replace(f'{sls.pending}/{category}/{log}', f'{sls.failed}/{category}/{log}')
                        elif result.code == sls.helpers.HelperResult.CLASS_ERROR:
                            break
                except Exception as e:
                    logger.error(f'Encountered error submitting logs for {category}', exc_info=e)
                    continue
        except LockHeldError:
            # Another process is currently working on this directory
            logger.warning(f'Lock already held trying to submit logs for {category}')
            continue
    logger.info('Finished log submission')
