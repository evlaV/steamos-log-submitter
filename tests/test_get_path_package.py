# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2025 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import subprocess
import steamos_log_submitter as sls
from . import count_hits  # NOQA: F401


def test_err(monkeypatch):
    def fake_subprocess(args, **kwargs):
        return subprocess.CompletedProcess(args, stdout="", stderr=f"No package owns {args[2]}\n", returncode=1)

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    assert sls.util.get_path_package("gordon") is None


def test_single(monkeypatch):
    def fake_subprocess(args, **kwargs):
        return subprocess.CompletedProcess(args, stdout=f"{args[2]} is owned by gman 2.0-1\n", stderr="", returncode=0)

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    assert sls.util.get_path_package("breen") == ("gman", "2.0-1")


def test_none(monkeypatch):
    def fake_subprocess(args, **kwargs):
        return subprocess.CompletedProcess(args, stdout="", stderr=f"No package owns {args[2]}\nNo package owns {args[3]}\n", returncode=1)

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    assert not sls.util.get_paths_packages(["gordon", "alyx"])


def test_dupe(monkeypatch):
    def fake_subprocess(args, **kwargs):
        return subprocess.CompletedProcess(args, stdout=f"{args[2]} is owned by gman 2.0-1\n{args[3]} is owned by gman 2.0-1\n", stderr="", returncode=0)

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    assert sls.util.get_paths_packages(["breen", "mossman"]) == {"gman": "2.0-1"}


def test_mixed(monkeypatch):
    def fake_subprocess(args, **kwargs):
        return subprocess.CompletedProcess(args, stdout=f"{args[2]} is owned by gman 2.0-1\n", stderr="No package owns {args[3]}\n", returncode=1)

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    assert sls.util.get_paths_packages(["breen", "gordon"]) == {"gman": "2.0-1"}


def test_batching(monkeypatch, count_hits):
    def fake_subprocess(args, **kwargs):
        count_hits()
        return subprocess.CompletedProcess(args, stdout=''.join([f"{arg} is owned by package{arg} 1.0-1\n" for arg in args[2:]]), stderr="", returncode=1)

    monkeypatch.setattr(subprocess, 'run', fake_subprocess)

    assert sls.util.get_paths_packages([str(x) for x in range(2000)]) == {f"package{x}": "1.0-1" for x in range(2000)}
    assert count_hits.hits == 2
