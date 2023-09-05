# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import logging.handlers
import steamos_log_submitter as sls
from typing import Optional

__all__ = [
    'reconfigure_logging',
]

config = sls.config.get_config(__name__)
logger = logging.getLogger(__name__)
root_logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')


def valid_level(level: str) -> bool:
    return level.upper() in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')


def add_handler(handler: logging.Handler, level: int) -> None:
    handler.setFormatter(formatter)
    handler.setLevel(level)
    root_logger.addHandler(handler)


def reconfigure_logging(path: Optional[str] = None, level: Optional[str] = None) -> None:
    level = (level or config.get('level') or 'WARNING').upper()
    if valid_level(level):
        level_int = getattr(logging, level)
    else:
        level_int = logging.WARNING

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    add_handler(logging.StreamHandler(), level_int)

    if path:
        try:
            add_handler(logging.handlers.TimedRotatingFileHandler(path, when='W6', backupCount=4, encoding='utf-8'), level_int)
        except OSError:
            logger.warning("Couldn't open log file")
    root_logger.setLevel(level_int)

    if level_int < logging.INFO:
        foreign_logger = logging.getLogger('asyncio')
        foreign_logger.setLevel(logging.INFO)
