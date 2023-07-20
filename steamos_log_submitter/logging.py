# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import logging.handlers
import steamos_log_submitter as sls

__all__ = [
    'reconfigure_logging',
]

config = sls.get_config(__name__)
logger = logging.getLogger(__name__)
root_logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')


def add_handler(handler: logging.Handler, level: int):
    handler.setFormatter(formatter)
    handler.setLevel(level)
    root_logger.addHandler(handler)


def reconfigure_logging(path: str = None):
    level = config.get('level', 'WARNING').upper()
    try:
        level = getattr(logging, level)
    except AttributeError:
        level = logging.WARNING

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    add_handler(logging.StreamHandler(), level)

    if path is None:
        path = config.get('path')
    if path:
        try:
            add_handler(logging.handlers.TimedRotatingFileHandler(path, when='W6', backupCount=4, encoding='utf-8'), level)
        except OSError:
            logger.warning("Couldn't open log file")
    root_logger.setLevel(level)
