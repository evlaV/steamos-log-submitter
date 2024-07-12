# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import os
import pytest

import steamos_log_submitter.aggregators.sentry as sentry
from steamos_log_submitter.helpers import HelperResult
from steamos_log_submitter.helpers.kdump import KdumpHelper as helper
from .. import custom_dsn, unreachable
from .. import fake_pwuid, mock_config  # NOQA: F401

file_base = f'{os.path.dirname(__file__)}/kdump'
dsn = custom_dsn('helpers.kdump')


def test_call_trace_parse():
    with open(f'{file_base}/stack.json') as f:
        stack_expected = json.load(f)
    with open(f'{file_base}/stack') as f:
        stack = f.read().rstrip().split('\n')
    assert stack_expected == helper.parse_traces(stack)


def test_call_trace_parse_strip_internal():
    with open(f'{file_base}/stack_internal.json') as f:
        stack_expected = json.load(f)
    with open(f'{file_base}/stack_internal') as f:
        stack = f.read().rstrip().split('\n')
    assert stack_expected == helper.parse_traces(stack)


def test_call_trace_parse3():
    with open(f'{file_base}/stack3.json') as f:
        stack_expected = json.load(f)
    with open(f'{file_base}/stack3') as f:
        stack = f.read().rstrip().split('\n')
    assert stack_expected == helper.parse_traces(stack)


def test_parse_irq():
    with open(f'{file_base}/stack_irq.json') as f:
        stack_expected = json.load(f)
    with open(f'{file_base}/stack_irq') as f:
        stack = f.read().rstrip().split('\n')
    assert stack_expected == helper.parse_traces(stack)


def test_dmesg_parse():
    with open(f'{file_base}/crash') as f:
        crash_expected = f.read()
    with open(f'{file_base}/stack') as f:
        stack_expected = f.read().rstrip().split('\n')
    with open(f'{file_base}/dmesg') as f:
        crash, stack, metadata = helper.get_summaries(f)
    assert crash == crash_expected
    assert stack == helper.parse_traces(stack_expected)
    assert metadata == {
        'kernel.modules': [
            'aesni_intel(E)',
            'atkbd(E)',
            'cdrom(E)',
            'cfg80211(E)',
            'crc16(E)',
            'crc32_pclmul(E)',
            'crc32c_generic(E)',
            'crc32c_intel(E)',
            'crct10dif_pclmul(E)',
            'cryptd(E)',
            'crypto_simd(E)',
            'dm_mod(E)',
            'drm_ttm_helper(E)',
            'ext4(E)',
            'failover(E)',
            'fat(E)',
            'fuse(E)',
            'gf128mul(E)',
            'ghash_clmulni_intel(E)',
            'i2c_i801(E)',
            'i2c_smbus(E)',
            'i8042(E)',
            'iTCO_vendor_support(E)',
            'iTCO_wdt(E)',
            'intel_agp(E)',
            'intel_gtt(E)',
            'intel_pmc_bxt(E)',
            'intel_rapl_common(E)',
            'intel_rapl_msr(E)',
            'ip_tables(E)',
            'irqbypass(E)',
            'jbd2(E)',
            'joydev(E)',
            'kvm(E)',
            'kvm_intel(E)',
            'libps2(E)',
            'loop(E)',
            'lp(OE+)',
            'lpc_ich(E)',
            'mac_hid(E)',
            'mbcache(E)',
            'mousedev(E)',
            'net_failover(E)',
            'parport(E)',
            'pcspkr(E)',
            'pkcs8_key_parser(E)',
            'pktcdvd(E)',
            'polyval_clmulni(E)',
            'polyval_generic(E)',
            'psmouse(E)',
            'qemu_fw_cfg(E)',
            'qxl(E)',
            'ramoops(E)',
            'rapl(E)',
            'reed_solomon(E)',
            'rfkill(E)',
            'serio(E)',
            'serio_raw(E)',
            'sha512_ssse3(E)',
            'sr_mod(E)',
            'ttm(E)',
            'vfat(E)',
            'virtio_balloon(E)',
            'virtio_blk(E)',
            'virtio_console(E)',
            'virtio_net(E)',
            'virtio_pci(E)',
            'virtio_pci_legacy_dev(E)',
            'virtio_pci_modern_dev(E)',
            'virtio_scsi(E)',
            'vivaldi_fmap(E)',
            'x_tables(E)',
        ]
    }


def test_dmesg_parse2():
    with open(f'{file_base}/crash2') as f:
        crash_expected = f.read()
    with open(f'{file_base}/stack2') as f:
        stack_expected = f.read().rstrip().split('\n')
    with open(f'{file_base}/dmesg2') as f:
        crash, stack, metadata = helper.get_summaries(f)
    print(json.dumps(stack, indent=2))
    print(json.dumps(helper.parse_traces(stack_expected), indent=2))
    assert crash == crash_expected
    assert stack == helper.parse_traces(stack_expected)
    assert metadata == {
        'kernel.modules': [
            '8250_dw',
            'ac97_bus',
            'acpi_cpufreq',
            'aesni_intel',
            'af_alg',
            'algif_aead',
            'algif_hash',
            'algif_skcipher',
            'amdgpu',
            'amdgpu_xcp_drv',
            'atkbd',
            'blake2b_generic',
            'bluetooth',
            'bnep',
            'bpf_preload',
            'btbcm',
            'btintel',
            'btmtk',
            'btrfs',
            'btrtl',
            'btusb',
            'cbc',
            'ccm',
            'ccp',
            'cdc_acm',
            'cec',
            'cfg80211',
            'cmac',
            'cqhci',
            'crc16',
            'crc32_pclmul',
            'crc32c_generic',
            'crc32c_intel',
            'crct10dif_pclmul',
            'cryptd',
            'crypto_simd',
            'crypto_user',
            'cs_dsp',
            'des_generic',
            'dm_mod',
            'drm_buddy',
            'drm_display_helper',
            'drm_ttm_helper',
            'dwc3_pci',
            'ecb',
            'ecdh_generic',
            'edac_mce_amd',
            'ext4',
            'extcon_steamdeck',
            'fat',
            'ff_memless',
            'fuse',
            'gf128mul',
            'ghash_clmulni_intel',
            'gpu_sched',
            'hid_microsoft',
            'hid_multitouch',
            'hid_steam',
            'hidp',
            'i2c_hid',
            'i2c_hid_acpi',
            'i2c_piix4',
            'i8042',
            'industrialio',
            'intel_rapl_common',
            'intel_rapl_msr',
            'ip6_tables',
            'ip6table_filter',
            'ip6table_mangle',
            'ip6table_nat',
            'ip6table_raw',
            'ip6table_security',
            'ip_tables',
            'iptable_filter',
            'iptable_mangle',
            'iptable_nat',
            'iptable_raw',
            'iptable_security',
            'irqbypass',
            'jbd2',
            'joydev',
            'kvm',
            'kvm_amd',
            'leds_steamdeck',
            'libarc4',
            'libcrc32c',
            'libdes',
            'libps2',
            'loop',
            'ltrf216a',
            'mac80211',
            'mac_hid',
            'mbcache',
            'md4',
            'mmc_block',
            'mmc_core',
            'mousedev',
            'nf_conntrack',
            'nf_defrag_ipv4',
            'nf_defrag_ipv6',
            'nf_nat',
            'nf_reject_ipv4',
            'nf_reject_ipv6',
            'nf_tables',
            'nfnetlink',
            'nft_chain_nat',
            'nft_ct',
            'nft_fib',
            'nft_fib_inet',
            'nft_fib_ipv4',
            'nft_fib_ipv6',
            'nft_reject',
            'nft_reject_inet',
            'nvme',
            'nvme_common',
            'nvme_core',
            'opt3001',
            'overlay',
            'pcspkr',
            'pkcs8_key_parser',
            'polyval_clmulni',
            'polyval_generic',
            'raid6_pq',
            'ramoops',
            'rapl',
            'reed_solomon',
            'rfkill',
            'rtw88_8822c',
            'rtw88_8822ce',
            'rtw88_core',
            'rtw88_pci',
            'sdhci',
            'sdhci_pci',
            'serio',
            'serio_raw',
            'sha512_ssse3',
            'snd',
            'snd_acp5x_i2s',
            'snd_acp5x_pcm_dma',
            'snd_acp_config',
            'snd_compress',
            'snd_hda_codec',
            'snd_hda_codec_hdmi',
            'snd_hda_core',
            'snd_hda_intel',
            'snd_hrtimer',
            'snd_hwdep',
            'snd_intel_dspcfg',
            'snd_intel_sdw_acpi',
            'snd_pci_acp5x',
            'snd_pcm',
            'snd_pcm_dmaengine',
            'snd_seq',
            'snd_seq_device',
            'snd_seq_dummy',
            'snd_soc_acp5x_mach',
            'snd_soc_acpi',
            'snd_soc_core',
            'snd_soc_cs35l41',
            'snd_soc_cs35l41_lib',
            'snd_soc_cs35l41_spi',
            'snd_soc_nau8821',
            'snd_soc_wm_adsp',
            'snd_sof',
            'snd_sof_amd_acp',
            'snd_sof_amd_vangogh',
            'snd_sof_pci',
            'snd_sof_utils',
            'snd_sof_xtensa_dsp',
            'snd_timer',
            'soundcore',
            'sp5100_tco',
            'spi_amd',
            'steamdeck',
            'steamdeck_hwmon',
            'tpm',
            'tpm_crb',
            'tpm_tis',
            'tpm_tis_core',
            'ttm',
            'uinput',
            'usbhid',
            'vfat',
            'video',
            'vivaldi_fmap',
            'wdat_wdt',
            'wmi',
            'x_tables',
            'xhci_pci',
            'xhci_pci_renesas',
            'xor',
        ]
    }


@pytest.mark.asyncio
async def test_submit_empty(monkeypatch):
    monkeypatch.setattr(sentry.SentryEvent, 'send', unreachable)
    assert await helper.submit(f'{file_base}/empty.zip') == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_submit_bad_zip(monkeypatch):
    monkeypatch.setattr(sentry.SentryEvent, 'send', unreachable)
    assert await helper.submit(f'{file_base}/bad.zip') == HelperResult.PERMANENT_ERROR


@pytest.mark.asyncio
async def test_submit_multiple_zip(monkeypatch):
    async def check_now(self) -> bool:
        assert len(self.attachments) == 3
        with open(f'{file_base}/stack.json') as f:
            assert self.exceptions == [{'stacktrace': frames, 'type': 'PANIC'} for frames in json.load(f)]
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    assert await helper.submit(f'{file_base}/dmesg-202310050102.zip') == HelperResult.OK


@pytest.mark.asyncio
async def test_submit_multiple_timestamp(monkeypatch):
    async def check_now(self) -> bool:
        assert self.timestamp == 1696467720
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    assert await helper.submit(f'{file_base}/dmesg-202310050102.zip') == HelperResult.OK


@pytest.mark.asyncio
async def test_submit_build_info(monkeypatch):
    async def check_now(self) -> bool:
        assert self.os_build == '20230927.1000'
        assert self.version == '3.6'
        assert self.tags['kernel'] == '6.1.52-valve2-1-neptune-61'
        return True

    monkeypatch.setattr(sentry.SentryEvent, 'send', check_now)
    assert await helper.submit(f'{file_base}/kdumpst-202310050540.zip') == HelperResult.OK


@pytest.mark.asyncio
async def test_collect_none():
    assert not await helper.collect()
