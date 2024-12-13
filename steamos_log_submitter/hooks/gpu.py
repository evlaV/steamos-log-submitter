#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import glob
import importlib.machinery
import json
import logging
import os
import re
import subprocess
import time
import typing
from typing import Union

import steamos_log_submitter as sls
import steamos_log_submitter.client
import steamos_log_submitter.helpers
from steamos_log_submitter.hooks import trigger
from steamos_log_submitter.logging import reconfigure_logging
from steamos_log_submitter.types import JSONEncodable

__loader__: importlib.machinery.SourceFileLoader
logger = logging.getLogger(__loader__.name)


async def run() -> None:
    ts = time.time_ns()
    env: dict[str, Union[str, int]] = {}
    log: dict[str, JSONEncodable] = {
        'timestamp': ts / 1_000_000_000,
        'kernel': os.uname().release,
        'branch': sls.util.get_steamos_branch(),
    }
    pid = None
    pci_path = None
    for key, val in os.environ.items():
        if key == 'PID':
            try:
                pid = int(val)
            except ValueError:
                pass
        if key == 'ID_PATH' and val.startswith('pci-'):
            pci_path = val[4:]
        env[key] = val
    log['env'] = env
    if pid:
        log['pid'] = pid
        appid = sls.util.get_appid(pid)
        if appid is not None:
            log['appid'] = appid
    else:
        for fcomm in glob.glob('/proc/*/comm'):
            try:
                with open(fcomm) as f:
                    comm = f.read()
            except OSError:
                continue
            if comm.rstrip() == 'reaper':
                try:
                    pid = int(fcomm.split('/')[2])
                except (ValueError, IndexError):
                    # This should never happen, but error checking is cheap
                    continue
                appid = sls.util.get_appid(pid)
                if appid is not None:
                    log['appid'] = appid
                    break
    try:
        executable = os.path.basename(os.readlink(f'/proc/{pid}/exe'))
        log['executable'] = executable
    except OSError:
        pass
    if env.get('NAME'):
        log['comm'] = env['NAME']
    try:
        mesa = subprocess.run(['pacman', '-Q', 'mesa'], capture_output=True, errors='replace', check=True)
        log['mesa'] = mesa.stdout.strip().split(' ')[1]
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning('Failed to get mesa version', exc_info=e)
        pass
    try:
        radv = subprocess.run(['pacman', '-Q', 'vulkan-radeon'], capture_output=True, errors='replace', check=True)
        log['radv'] = radv.stdout.strip().split(' ')[1]
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning('Failed to get vulkan-radeon version', exc_info=e)
        pass
    journal, _ = await sls.util.read_journal('kernel', current_boot=True, start_ago_ms=15000)
    ring = None
    if journal:
        ring_re = re.compile(r'\*ERROR\* ring ([^ ]+) timeout')
        relevant: list[str] = []
        for line in journal:
            for context in ('amdgpu', 'drm', 'i915', 'nouveau'):
                message = typing.cast(str, line.get('MESSAGE', ''))
                if context in message:
                    relevant.append(message)
                    if context == 'amdgpu':
                        match = ring_re.search(message)
                        if match:
                            ring = match.group(1)
                    break
        log['journal'] = relevant
    if pci_path is not None and ring is not None:
        umr_log = {}
        try:
            umr = subprocess.run(['umr', '--by-pci', pci_path, '-O', 'bits,halt_waves', '-go', '0', '-wa', ring, '-go', '1'], capture_output=True, errors='replace', check=True)
            umr_log['wave'] = {'stdout': umr.stdout}
            if umr.stderr:
                umr_log['wave']['stderr'] = umr.stderr
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning('Failed to get wave information via umr', exc_info=e)
            pass
        try:
            umr = subprocess.run(['umr', '--by-pci', pci_path, '-RS', 'gfx_0.0.0'], capture_output=True, errors='replace', check=True)
            umr_log['ring'] = {'stdout': umr.stdout}
            if umr.stderr:
                umr_log['ring']['stderr'] = umr.stderr
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning('Failed to get ring information via umr', exc_info=e)
            pass
        if umr_log:
            log['umr'] = umr_log
    with sls.helpers.StagingFile('gpu', f'{ts}.json', 'w') as f:
        json.dump(log, f)


if __name__ == '__main__':  # pragma: no cover
    reconfigure_logging('/var/log/steamos-log-submitter/gpu-crash.log', remote=True)
    try:
        asyncio.run(run())
        trigger('gpu')
    except Exception as e:
        logger.critical('Unhandled exception', exc_info=e)
