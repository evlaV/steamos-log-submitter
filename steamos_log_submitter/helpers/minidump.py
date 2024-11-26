# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import os
import minidump.aminidumpfile  # type: ignore[import-untyped]
import minidump.common_structs  # type: ignore[import-untyped]
from minidump.exceptions import (  # type: ignore[import-untyped]
    MinidumpException, MinidumpHeaderSignatureMismatchException, MinidumpHeaderFlagsException)
from typing import Final
from steamos_log_submitter.aggregators.sentry import MinidumpEvent
from . import Helper, HelperResult

# Extra stream types
# Breakpad extensions (Gg)
MD_RAW_BREAKPAD_INFO: Final[int] = 0x47670001
MD_RAW_ASSERTION_INFO: Final[int] = 0x47670002
MD_LINUX_CPU_INFO: Final[int] = 0x47670003
MD_LINUX_PROC_STATUS: Final[int] = 0x47670004
MD_LINUX_LSB_RELEASE: Final[int] = 0x47670005
MD_LINUX_CMD_LINE: Final[int] = 0x47670006
MD_LINUX_ENVIRON: Final[int] = 0x47670007
MD_LINUX_AUXV: Final[int] = 0x47670008
MD_LINUX_MAPS: Final[int] = 0x47670009
MD_LINUX_DSO_DEBUG: Final[int] = 0x4767000a
# Crashpad extensions (CP)
MD_CRASHPAD_INFO_STREAM: Final[int] = 0x43500001


class MinidumpHelper(Helper):
    valid_extensions = frozenset({'.md', '.dmp'})

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        name, _ = os.path.splitext(os.path.basename(fname))
        name_parts = name.split('-')

        event = MinidumpEvent(cls.config['dsn'])
        try:
            event.appid = int(name_parts[-1])
        except ValueError:
            # Invalid appid
            pass

        for attr in ('executable', 'comm', 'path', 'build_id', 'pkgname', 'pkgver'):
            try:
                event.tags[attr] = os.getxattr(fname, f'user.{attr}').decode(errors='replace')
            except OSError:
                cls.logger.warning(f'Failed to get {attr} xattr on minidump.')

        if 'executable' in event.tags:
            event.fingerprint.append(f'executable:{event.tags["executable"]}')

        try:
            mf = await minidump.aminidumpfile.AMinidumpFile.parse(fname)

            for i in range(mf.header.NumberOfStreams):
                await mf.file_handle.seek(mf.header.StreamDirectoryRva + i * 12, os.SEEK_SET)
                type = await mf.file_handle.read(4)
                type_value = int.from_bytes(type, byteorder='little', signed=False)
                if type_value == MD_LINUX_ENVIRON:
                    loc = await minidump.common_structs.MINIDUMP_LOCATION_DESCRIPTOR.aparse(mf.file_handle)
                    await mf.file_handle.seek(loc.Rva)
                    environ = await mf.file_handle.read(loc.DataSize)
                    if environ:
                        ev = {}
                        for envvar in environ.split(b'\0'):
                            if not envvar:
                                continue
                            try:
                                key, value = envvar.split(b'=', 1)
                            except ValueError:
                                cls.logger.warning(f'Got invalid environment variable: {envvar}')
                                continue
                            ev[key.decode(errors='replace')] = value.decode(errors='replace')
                        event.extra['environ'] = ev
        except (MinidumpException, MinidumpHeaderSignatureMismatchException, MinidumpHeaderFlagsException) as e:
            cls.logger.warning(f"Couldn't parse minidump, skipping extra data: {e}")

        cls.logger.debug(f'Uploading minidump {fname}')
        try:
            with open(fname, 'rb') as f:
                return HelperResult.check(await event.send_minidump(f))
        except ValueError:
            return HelperResult.PERMANENT_ERROR
