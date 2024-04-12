# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import pytest
import zipfile
import steamos_log_submitter.aggregators.sentry as sentry
from steamos_log_submitter.helpers import HelperResult
from steamos_log_submitter.helpers.devcoredump import DevcoredumpHelper as helper
from .. import custom_dsn
from .. import helper_directory, mock_config, patch_module  # NOQA: F401

dsn = custom_dsn('helpers.devcoredump')


@pytest.mark.asyncio
async def test_invalid_zip(helper_directory):
    with open(f'{helper_directory}/fake.zip', 'wb') as _:
        pass

    assert await helper.submit(f'{helper_directory}/fake.zip') == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_missing_metadata(helper_directory):
    with zipfile.ZipFile(f'{helper_directory}/fake.zip', 'w'):
        pass

    assert await helper.submit(f'{helper_directory}/fake.zip') == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_invalid_metadata(helper_directory):
    with zipfile.ZipFile(f'{helper_directory}/fake.zip', 'w') as zf:
        with zf.open('metadata.json', 'w'):
            pass

    assert await helper.submit(f'{helper_directory}/fake.zip') == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_submit_params_base(helper_directory, mock_config, monkeypatch):
    async def fake_submit(self):
        assert len(self.attachments) == 2
        assert self.attachments[0]['mime-type'] == 'application/zip'
        assert self.attachments[0]['filename'] == 'fake.zip'
        assert self.attachments[1]['mime-type'] == 'application/json'
        assert self.attachments[1]['filename'] == 'metadata.json'
        assert self.message == 'Unknown device'
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', fake_submit)

    with zipfile.ZipFile(f'{helper_directory}/fake.zip', 'w') as zf:
        with zf.open('metadata.json', 'w') as f:
            f.write(b'{}')

    assert await helper.submit(f'{helper_directory}/fake.zip') == HelperResult.OK


@pytest.mark.asyncio
async def test_submit_params_all(helper_directory, mock_config, monkeypatch):
    async def fake_submit(self):
        assert len(self.attachments) == 2
        assert self.attachments[0]['mime-type'] == 'application/zip'
        assert self.attachments[0]['filename'] == 'fake.zip'
        assert self.attachments[1]['mime-type'] == 'application/json'
        assert self.attachments[1]['filename'] == 'metadata.json'
        assert self.timestamp == 1.25
        assert self.tags['kernel'] == '6.1.52'
        assert self.tags['branch'] == 'main'
        assert self.tags['failing_device'] == '/pci/hev'
        assert self.tags['driver'] == 'xen'
        assert self.fingerprint == ['driver:xen']
        assert self.message == 'xen: /pci/hev'
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', fake_submit)

    with zipfile.ZipFile(f'{helper_directory}/fake.zip', 'w') as zf:
        with zf.open('metadata.json', 'w') as f:
            f.write(json.dumps({
                'timestamp': 1.25,
                'kernel': '6.1.52',
                'branch': 'main',
                'failing_device': '/pci/hev',
                'driver': 'xen',
            }).encode())

    assert await helper.submit(f'{helper_directory}/fake.zip') == HelperResult.OK
