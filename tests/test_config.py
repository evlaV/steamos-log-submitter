import builtins
import configparser
import io
import os
import steamos_log_submitter.config as config

file_base = f'{os.path.dirname(__file__)}/config'


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
    monkeypatch.setattr(config, 'local_config_path', 'cfg')
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


def test_reload_config_no_base(monkeypatch):
    fake_path = 'fake_path'
    hit = False

    def bad_open(path, *args, **kwargs):
        nonlocal hit
        if path == fake_path:
            hit = True
        raise FileNotFoundError

    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', fake_path)
    monkeypatch.setattr(builtins, 'open', bad_open)

    config.reload_config()
    assert hit
    assert not config.config.has_section('sls')


def test_reload_config_base(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', f'{file_base}/base.cfg')

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'base')
    assert config.config.get('sls', 'base') == '/fake'


def test_reload_config_user(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', f'{file_base}/base-user.cfg')
    monkeypatch.chdir(file_base)

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'user-config')
    assert config.config.get('sls', 'user-config') == 'user.cfg'

    assert config.config.has_option('sls', 'extra')
    assert config.config.get('sls', 'extra') == 'yes'


def test_reload_config_local(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'local_config_path', None)
    monkeypatch.setattr(config, 'base_config_path', f'{file_base}/base-local.cfg')
    monkeypatch.chdir(file_base)

    config.reload_config()

    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'local-config')
    assert config.config.get('sls', 'local-config') == 'local.cfg'
    assert config.local_config_path == 'local.cfg'

    assert not config.config.has_option('sls', 'local')
    assert config.local_config.has_section('sls')
    assert config.local_config.has_option('sls', 'local')
    assert config.local_config.get('sls', 'local') == 'yes'


def test_reload_config_interpolation(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', f'{file_base}/interpolation.cfg')

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'base')
    assert config.config.get('sls', 'base') == '/fake'
    assert config.config.get('sls', 'subdir') == '/fake/dir'

# vim:ts=4:sw=4:et
