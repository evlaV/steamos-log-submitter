# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import logging
import os
from collections.abc import Iterable

import steamos_log_submitter as sls
import steamos_log_submitter.helpers
from steamos_log_submitter.lockfile import LockHeldError

logger = logging.getLogger(__name__)


async def collect_category(helper: sls.helpers.Helper) -> list[str]:
    logger.info(f'Collecting logs for {helper.name}')
    try:
        with helper.lock():
            return await helper.collect()
    except LockHeldError:
        # Another process is currently working on this directory
        logger.warning(f'Lock already held trying to collect logs for {helper.name}')
    except Exception as e:
        logger.error(f'Encountered error collecting logs for {helper.name}', exc_info=e)
    return []


async def collect() -> list[str]:
    if sls.base_config.get('collect', 'on') != 'on':
        return []
    logger.info('Starting log collection')
    tasks = []
    logs = []
    for category in sls.helpers.list_helpers():
        helper = sls.helpers.create_helper(category)
        if not helper:
            continue

        if not helper.enabled() or not helper.collect_enabled():
            continue

        async def collect_fn(helper: sls.helpers.Helper) -> list[str]:
            collected = await collect_category(helper)
            return [f'{helper.name}/{log}' for log in collected]

        tasks.append(asyncio.create_task(collect_fn(helper)))
    if tasks:
        done, _ = await asyncio.wait(tasks)
        for task in done:
            logs.extend(task.result())
    logger.info('Finished log collection')
    return logs


async def submit_category(helper: sls.helpers.Helper, logs: Iterable[str]) -> list[str]:
    submitted = []
    try:
        with helper.lock():
            for log in logs:
                if log.startswith('.'):
                    continue
                logger.debug(f'Found log {helper.name}/{log}')
                result = await helper.submit(f'{sls.pending}/{helper.name}/{log}')
                if result == sls.helpers.HelperResult.OK:
                    logger.debug(f'Succeeded in submitting {helper.name}/{log}')
                    submitted.append(log)
                    os.replace(f'{sls.pending}/{helper.name}/{log}', f'{sls.uploaded}/{helper.name}/{log}')
                else:
                    logger.warning(f'Failed to submit log {helper.name}/{log} with code {result}')
                if result == sls.helpers.HelperResult.PERMANENT_ERROR:
                    os.replace(f'{sls.pending}/{helper.name}/{log}', f'{sls.failed}/{helper.name}/{log}')
                elif result == sls.helpers.HelperResult.CLASS_ERROR:
                    break
    except LockHeldError:
        # Another process is currently working on this directory
        logger.warning(f'Lock already held trying to submit logs for {helper.name}')
    except Exception as e:
        logger.error(f'Encountered error submitting logs for {helper.name}', exc_info=e)
    return submitted


async def submit() -> list[str]:
    if sls.base_config.get('submit', 'on') != 'on':
        return []
    logger.info('Starting log submission')
    if not sls.util.check_network():
        logger.info('Network is offline, bailing out')
        return []

    tasks = []
    submitted = []
    for category in sls.helpers.list_helpers():
        helper = sls.helpers.create_helper(category)
        if not helper:
            continue

        if not helper.enabled() or not helper.submit_enabled():
            continue
        logger.info(f'Submitting logs for {category}')
        logs = helper.list_pending()

        if not logs:
            logger.info('No logs found, skipping')
            continue

        async def submit_fn(helper: sls.helpers.Helper, logs: Iterable[str]) -> list[str]:
            submitted = await submit_category(helper, logs)
            return [f'{helper.name}/{log}' for log in submitted]

        tasks.append(asyncio.create_task(submit_fn(helper, logs)))
    if tasks:
        done, _ = await asyncio.wait(tasks)
        for task in done:
            submitted.extend(task.result())
    logger.info('Finished log submission')
    return submitted


async def trigger() -> tuple[list[str], list[str]]:
    collected = []
    submitted = []
    if sls.base_config['enable'] == 'on':
        logger.info('Routine collection/submission triggered')
        try:
            collected = await collect()
        except Exception as e:
            logger.critical('Unhandled exception while collecting logs', exc_info=e)
        try:
            submitted = await submit()
        except Exception as e:
            logger.critical('Unhandled exception while submitting logs', exc_info=e)
    else:
        logger.debug('Routine collection/submission is disabled')
    return collected, submitted
