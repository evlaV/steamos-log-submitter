# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import subprocess
import steamos_log_submitter as sls
from . import always_raise


def test_success(monkeypatch):
    def fake_subprocess(*args, **kwargs):
        ret: subprocess.CompletedProcess = subprocess.CompletedProcess(args[0], 0)
        ret.stdout = 'main\n'
        return ret

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)
    assert sls.util.get_steamos_branch() == 'main'


def test_failure(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', always_raise(subprocess.SubprocessError))
    assert sls.util.get_steamos_branch() is None
