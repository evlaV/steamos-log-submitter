# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
from .lockfile import Lockfile, LockHeldError
from steamos_log_submitter.config import get_config
from steamos_log_submitter.logging import reconfigure_logging
import steamos_log_submitter.util as util

import importlib
import logging
import os

__all__ = [
    # Constants
    'base',
    'pending',
    'uploaded',
    # Utility functions
    'submit',
    'trigger',
    'get_config',
    # Submodules
    'util',
]

base_config = get_config(__name__, defaults={
    'enable': 'off',
    'base': '/var/lib/steamos-log-submitter',
})

base = base_config['base']
pending = f'{base}/pending'
uploaded = f'{base}/uploaded'

reconfigure_logging()


class HelperError(RuntimeError):
    pass


def trigger():
    print(logging)
    if base_config['enable'] == 'on':
        logging.info('Routine collection/submission triggered')
        try:
            collect()
        except Exception as e:
            logging.critical('Unhandled exception while collecting logs', exc_info=e)
        try:
            submit()
        except Exception as e:
            logging.critical('Unhandled exception while submitting logs', exc_info=e)


def create_helper(category):
    try:
        helper = importlib.import_module(f'steamos_log_submitter.helpers.{category}')
        if not hasattr(helper, 'submit'):
            raise HelperError('Helper module does not contain submit function')
    except ModuleNotFoundError as e:
        raise HelperError from e
    return helper


def collect():
    logging.info('Starting log collection')
    for category in os.listdir(pending):
        cat_config = get_config(f'steamos_log_submitter.helpers.{category}')
        if cat_config.get('enable', 'on') != 'on' or cat_config.get('collect', 'on') != 'on':
            continue
        logging.info(f'Collecting logs for {category}')
        try:
            with Lockfile(f'{pending}/{category}/.lock'):
                helper = create_helper(category)
                helper.collect()
        except LockHeldError:
            # Another process is currently working on this directory
            logging.warning(f'Lock already held trying to collect logs for {category}')
            continue
    logging.info('Finished log collection')


def submit():
    logging.info('Starting log submission')
    if not util.check_network():
        logging.info('Network is offline, bailing out')
        return

    for category in os.listdir(pending):
        cat_config = get_config(f'steamos_log_submitter.helpers.{category}')
        if cat_config.get('enable', 'on') != 'on' or cat_config.get('submit', 'on') != 'on':
            continue
        logging.info('Submitting logs for {category}')
        try:
            logs = os.listdir(f'{pending}/{category}')
        except IOError as e:
            logging.error(f'Encountered error listing logs for {category}', exc_info=e)
            continue

        if not logs:
            logging.info('No logs found, skipping')
            continue

        try:
            with Lockfile(f'{pending}/{category}/.lock'):
                try:
                    helper = create_helper(category)
                    for log in logs:
                        if log.startswith('.'):
                            continue
                        logging.debug(f'Found log {category}/{log}')
                        if helper.submit(f'{pending}/{category}/{log}'):
                            logging.debug(f'Succeeded in submitting {category}/{log}')
                            os.replace(f'{pending}/{category}/{log}', f'{uploaded}/{category}/{log}')
                        else:
                            logging.warning(f'Failed to submit log {category}/{log}')
                except HelperError as e:
                    logging.error('Encountered error with helper', exc_info=e)
                    continue
        except LockHeldError:
            # Another process is currently working on this directory
            logging.warning(f'Lock already held trying to submit logs for {category}')
            continue
    logging.info('Finished log submission')

# vim:ts=4:sw=4:et
