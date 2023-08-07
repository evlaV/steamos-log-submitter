#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter as sls


def trigger() -> None:
    with sls.util.drop_root():
        sls.trigger()
