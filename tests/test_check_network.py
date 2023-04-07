# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import requests
import time
import steamos_log_submitter as sls
from . import fake_request


def sleepless(*args, **kwargs):
    pass


def test_204(monkeypatch):
    monkeypatch.setattr(requests, 'head', fake_request(204))
    monkeypatch.setattr(time, 'sleep', sleepless)
    assert sls.util.check_network() is True


def test_200(monkeypatch):
    def ret_200(*args, **kwargs):
        r = requests.Response()
        r.status_code = 200
        return r

    monkeypatch.setattr(requests, 'head', fake_request(200))
    monkeypatch.setattr(time, 'sleep', sleepless)
    assert sls.util.check_network() is False


def test_200_to_204(monkeypatch):
    i = 0

    def ret_200_to_204(*args, **kwargs):
        nonlocal i
        r = requests.Response()
        if i == 3:
            r.status_code = 204
        else:
            r.status_code = 200
        i += 1
        return r

    monkeypatch.setattr(requests, "head", ret_200_to_204)
    monkeypatch.setattr(time, "sleep", sleepless)
    assert sls.util.check_network() is True


def test_raise(monkeypatch):
    def ret_raise(*args, **kwargs):
        raise Exception()

    monkeypatch.setattr(requests, "head", ret_raise)
    monkeypatch.setattr(time, "sleep", sleepless)
    assert sls.util.check_network() is False


def test_raise_to_204(monkeypatch):
    i = 0

    def ret_raise_to_204(*args, **kwargs):
        nonlocal i
        r = requests.Response()
        i += 1
        if i == 4:
            r.status_code = 204
        else:
            raise Exception()
        return r

    monkeypatch.setattr(requests, "head", ret_raise_to_204)
    monkeypatch.setattr(time, "sleep", sleepless)
    assert sls.util.check_network() is True
