import configparser
import steamos_log_submitter as sls
import steamos_log_submitter.config as config
from . import unreachable

def setup_conf(monkeypatch, enable=None):
    testconf = configparser.ConfigParser()
    monkeypatch.setattr(config, 'config', testconf)
    localconf = configparser.ConfigParser()

    if enable is not None:
        localconf.add_section('sls')
        localconf.set('sls', 'enable', enable)
    monkeypatch.setattr(config, 'local_config', localconf)

def test_config_missing(monkeypatch):
    setup_conf(monkeypatch)
    monkeypatch.setattr(sls, 'collect', unreachable)
    monkeypatch.setattr(sls, 'submit', unreachable)
    sls.trigger()


def test_config_off(monkeypatch):
    setup_conf(monkeypatch, 'off')
    monkeypatch.setattr(sls, 'collect', unreachable)
    monkeypatch.setattr(sls, 'submit', unreachable)
    sls.trigger()


def test_config_invalid(monkeypatch):
    setup_conf(monkeypatch, 'foo')
    monkeypatch.setattr(sls, 'collect', unreachable)
    monkeypatch.setattr(sls, 'submit', unreachable)
    sls.trigger()


def test_config_on(monkeypatch):
    hit = 0
    def do_hit():
        nonlocal hit
        hit += 1
    setup_conf(monkeypatch, 'on')
    monkeypatch.setattr(sls, 'collect', do_hit)
    monkeypatch.setattr(sls, 'submit', do_hit)
    sls.trigger()
    assert hit == 2


# vim:ts=4:sw=4:et
