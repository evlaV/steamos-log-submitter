# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import abc

from steamos_log_submitter.helpers import HelperResult


class AggregatorEvent(abc.ABC):
    @abc.abstractmethod
    def seal(self) -> None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    async def send(self) -> HelperResult:  # pragma: no cover
        raise NotImplementedError
