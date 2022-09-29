# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import os
import time
import steamos_log_submitter as sls
from steamos_log_submitter.crash import upload as upload_crash


def collect() -> bool:
    return False


def submit(fname: str) -> bool:
    name, ext = os.path.splitext(os.path.basename(fname))
    if ext != '.log':
        return False

    try:
        with open(fname) as f:
            note = f.read()
    except IOError:
        return False

    timestamp = None
    for line in note.split('\n'):
        if not line.startswith('TIMESTAMP='):
            continue
        try:
            timestamp = int(line.split('=')[1])
        except ValueError:
            break

    if not timestamp:
        timestamp = time.time_ns()

    info = {
        'crash_time': timestamp // 1_000_000_000,
        'stack': '',
        'note': note,
    }
    if not upload_crash(product='holo-gpu', build=sls.util.get_build_id(), version=os.uname().release, info=info):
        return False

    return True

# vim:ts=4:sw=4:et
