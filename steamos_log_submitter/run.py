# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
if __name__ == '__main__':  # pragma: no cover
    import logging
    import os
    import psutil
    from . import trigger

    logger = logging.getLogger(__name__)
    try:
        os.nice(19)
        psutil.Process().ionice(psutil.IOPRIO_CLASS_IDLE)
    except OSError as e:
        logger.warning('Failed to downgrade process priority', exc_info=e)
    trigger()
