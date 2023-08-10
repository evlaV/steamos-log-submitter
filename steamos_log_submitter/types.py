# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Optional, TypeAlias, Union

DBusEncodable: TypeAlias = Sequence['DBusEncodable'] | Mapping[Union[str, int], 'DBusEncodable'] | tuple['DBusEncodable', ...] | bool | float | int | str
DBusCallable: TypeAlias = Callable[..., Union[Optional[DBusEncodable], Awaitable[Optional[DBusEncodable]]]]
JSON: TypeAlias = list['JSON'] | dict[str, 'JSON'] | bool | float | int | str | None
JSONEncodable: TypeAlias = Sequence['JSONEncodable'] | Mapping[str, 'JSONEncodable'] | JSON
