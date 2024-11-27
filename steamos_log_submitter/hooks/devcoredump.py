#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import importlib.machinery
import json
import logging
import os
import sys
import time
import typing
import zipfile

import steamos_log_submitter as sls
import steamos_log_submitter.client
from steamos_log_submitter.hooks import trigger
from steamos_log_submitter.logging import reconfigure_logging
from steamos_log_submitter.types import JSONEncodable

__loader__: importlib.machinery.SourceFileLoader
logger = logging.getLogger(__loader__.name)


async def run() -> bool:
    driver_blocklist = ('amdgpu',  # amdgpu is handled by the gpu hook
                        'ath11k_pci', )  # ath11k_pci is handled by steamos-manager

    ts = time.time_ns()
    dumpdir = sys.argv[1]
    logger.info(f'Found dump at {dumpdir}')
    failing_dev = None
    driver = None
    metadata: dict[str, JSONEncodable] = {
        'timestamp': ts / 1_000_000_000,
        'kernel': os.uname().release,
        'branch': sls.util.get_steamos_branch(),
    }
    try:
        failing_dev = os.readlink(f'{dumpdir}/failing_device')
        failing_dev = os.path.abspath(failing_dev)
        metadata['failing_device'] = failing_dev
    except OSError as e:
        logger.warning(f'Failed to canonicalize device path: {e}')
    try:
        driver = os.path.basename(os.readlink(f'{dumpdir}/failing_device/driver'))
        metadata['driver'] = driver
    except OSError as e:
        logger.error(f'Failed to determine failing device driver: {e}')

    if driver in driver_blocklist:
        return False

    journal = None
    if driver is not None:
        journal, _ = await sls.util.read_journal('kernel', current_boot=True, start_ago_ms=15000)
    if journal is not None:
        assert driver is not None  # This shouldn't be needed--it appears to be a mypy bug?
        relevant: list[str] = []
        for line in journal:
            if driver in typing.cast(str, line.get('MESSAGE', '')):
                relevant.append(typing.cast(str, line['MESSAGE']))
        metadata['journal'] = relevant

    if failing_dev is not None:
        devname = failing_dev.removeprefix('/sys')
        devname = devname.removeprefix('/')
        devname = devname.replace('/', '_')

    if failing_dev is None:
        filename = f'unknown-{ts}.zip'
    elif driver is None:
        filename = f'{devname}-{ts}.zip'
    else:
        filename = f'{driver}-{devname}-{ts}.zip'

    with sls.helpers.StagingFile('devcoredump', filename, 'wb') as f:
        with zipfile.ZipFile(f, mode='x', compression=zipfile.ZIP_DEFLATED) as zf:
            with zf.open('metadata.json', 'w') as zff:
                zff.write(json.dumps(metadata).encode())
            with zf.open('dump', 'w') as zff:
                with open(f'{dumpdir}/data', 'rb') as dump:
                    while True:
                        block = dump.read(4096)
                        if not block:
                            break
                        zff.write(block)

    return True


if __name__ == '__main__':  # pragma: no cover
    reconfigure_logging('/var/log/steamos-log-submitter/devcoredump.log', remote=True)
    try:
        if asyncio.run(run()):
            trigger('devcoredump')
    except Exception as e:
        logger.critical('Unhandled exception', exc_info=e)
