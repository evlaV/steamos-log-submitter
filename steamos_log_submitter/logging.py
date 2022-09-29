# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import steamos_log_submitter as sls

config = sls.get_config(__name__)


def reconfigure_logging():
    level = config.get('level', 'WARNING').upper()
    try:
        level = getattr(logging, level)
    except AttributeError:
        level = logging.WARNING

    kwargs = {
        'encoding': 'utf-8',
        'level': level,
        'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'
    }

    path = config.get('path')
    if path:
        kwargs['filename'] = path

    logging.basicConfig(**kwargs)

# vim:ts=4:sw=4:et
