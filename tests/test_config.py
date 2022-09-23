import builtins
import configparser
import io
import steamos_log_submitter.config as config


def test_section_get_no_val_no_default(monkeypatch):
    testconf = configparser.ConfigParser()
    monkeypatch.setattr(config, 'config', testconf)
    section = config.ConfigSection('test')
    try:
        section['nothing']
        assert False
    except KeyError:
        pass


def test_section_get_val_no_default(monkeypatch):
    testconf = configparser.ConfigParser()
    testconf.add_section('test')
    testconf.set('test', 'nothing', '1')
    monkeypatch.setattr(config, 'config', testconf)
    section = config.ConfigSection('test')
    try:
        assert section['nothing'] == '1'
    except KeyError:
        assert False


def test_section_get_no_section_default(monkeypatch):
    testconf = configparser.ConfigParser()
    monkeypatch.setattr(config, 'config', testconf)
    section = config.ConfigSection('test', defaults={'nothing': True})
    try:
        assert section['nothing']
    except KeyError:
        assert False


def test_section_get_no_val_default(monkeypatch):
    testconf = configparser.ConfigParser()
    testconf.add_section('test')
    monkeypatch.setattr(config, 'config', testconf)
    section = config.ConfigSection('test', defaults={'nothing': True})
    try:
        assert section['nothing']
    except KeyError:
        assert False


def test_section_get_val_default(monkeypatch):
    testconf = configparser.ConfigParser()
    testconf.add_section('test')
    testconf.set('test', 'nothing', '1')
    monkeypatch.setattr(config, 'config', testconf)
    section = config.ConfigSection('test', defaults={'nothing': '0'})
    try:
        assert section['nothing'] == '1'
    except KeyError:
        assert False


def test_local_setting(monkeypatch):
    monkeypatch.setattr(config, 'local_config', configparser.ConfigParser())
    section = config.ConfigSection('test')
    try:
        section['nothing']
        assert False
    except KeyError:
        pass

    section['nothing'] = '1'
    try:
        assert section['nothing'] == '1'
    except KeyError:
        assert False


def test_write_setting(monkeypatch):
    class MockIO(io.StringIO):
        def close(self):
            self.finalvalue = self.getvalue()
            super(MockIO, self).close()

    def fake_open(io):
        def ret(path, mode):
            return io
        return ret

    first = MockIO()
    second = MockIO()

    testconf = configparser.ConfigParser(delimiters='=')
    monkeypatch.setattr(config, 'local_config', testconf)
    section = config.ConfigSection('test')

    monkeypatch.setattr(builtins, 'open', fake_open(first))
    config.write_config()
    assert not first.finalvalue

    monkeypatch.setattr(builtins, 'open', fake_open(second))
    section['nothing'] = '1'
    config.write_config()
    assert second.finalvalue == """[test]
nothing = 1

"""


def test_get_config_out_of_scope():
    try:
        config.get_config('builtins')
        assert False
    except KeyError:
        pass


def test_get_config_no_section(monkeypatch):
    testconf = configparser.ConfigParser()
    monkeypatch.setattr(config, 'config', testconf)
    section = config.get_config('steamos_log_submitter.foo')
    assert section
    assert not testconf.has_section('foo')

# vim:ts=4:sw=4:et
