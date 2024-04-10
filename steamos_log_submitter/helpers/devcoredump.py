# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
from . import Helper, HelperResult


class DevcoredumpHelper(Helper):
    valid_extensions = frozenset({'.zip'})

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        return HelperResult.PERMANENT_ERROR
