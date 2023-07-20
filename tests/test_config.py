# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import builtins
import configparser
import io
import os
import pwd
import steamos_log_submitter as sls
import steamos_log_submitter.config as config
from . import CustomConfig
from . import always_raise, fake_pwuid  # NOQA: F401

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


def test_section_contains(monkeypatch):
    testconf = configparser.ConfigParser()
    testconf.add_section('test')
    monkeypatch.setattr(config, 'config', testconf)
    section = config.ConfigSection('test')
    assert 'foo' not in section
    testconf.set('test', 'foo', '1')
    assert 'foo' in section


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


def test_local_contains(monkeypatch):
    monkeypatch.setattr(config, 'local_config', configparser.ConfigParser())
    section = config.ConfigSection('test')
    assert 'nothing' not in section
    section['nothing'] = '1'
    assert 'nothing' in section


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


def test_reload_config_uid(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', 'base-uid.cfg')
    monkeypatch.chdir(file_base)

    real_open = open

    def open_uid(fname):
        if fname == 'base-uid.cfg':
            return real_open(fname)
        assert fname == '/home/1000/.steam/root/config/steamos-log-submitter.cfg'
        return real_open('user.cfg')
    monkeypatch.setattr(builtins, 'open', open_uid)

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'uid')
    assert config.config.get('sls', 'uid') == '1000'

    assert config.config.has_option('sls', 'extra')
    assert config.config.get('sls', 'extra') == 'yes'


def test_reload_config_bad_uid(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', 'base-uid.cfg')
    monkeypatch.setattr(pwd, 'getpwuid', always_raise(KeyError))
    monkeypatch.chdir(file_base)

    real_open = open

    def open_uid(fname):
        assert fname == 'base-uid.cfg'
        return real_open(fname)
    monkeypatch.setattr(builtins, 'open', open_uid)

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'uid')
    assert config.config.get('sls', 'uid') == '1000'

    assert not config.config.has_option('sls', 'extra')


def test_reload_config_nonnumeric_uid(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', 'base-uid-nonnumeric.cfg')
    monkeypatch.setattr(pwd, 'getpwuid', always_raise(KeyError))
    monkeypatch.chdir(file_base)

    real_open = open

    def open_uid(fname):
        assert fname == 'base-uid-nonnumeric.cfg'
        return real_open(fname)
    monkeypatch.setattr(builtins, 'open', open_uid)

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'uid')
    assert config.config.get('sls', 'uid') == 'steam'

    assert not config.config.has_option('sls', 'extra')


def test_reload_config_uid_user(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', 'base-uid-user.cfg')
    monkeypatch.chdir(file_base)

    real_open = open

    def open_uid(fname):
        if fname == 'base-uid-user.cfg':
            return real_open(fname)
        assert fname == 'user.cfg'
        return real_open('user.cfg')
    monkeypatch.setattr(builtins, 'open', open_uid)

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'uid')
    assert config.config.get('sls', 'uid') == '1000'
    assert config.config.get('sls', 'user-config') == 'user.cfg'

    assert config.config.has_option('sls', 'extra')
    assert config.config.get('sls', 'extra') == 'yes'


def test_reload_config_user_missing(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', f'{file_base}/base-user.cfg')

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'user-config')
    assert config.config.get('sls', 'user-config') == 'user.cfg'

    assert not config.config.has_option('sls', 'extra')


def test_reload_config_user_inaccessible(monkeypatch):
    fake_path = 'user.cfg'
    hit = False

    real_open = open

    def bad_open(path, *args, **kwargs):
        nonlocal hit
        if path == fake_path:
            hit = True
            raise PermissionError
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', f'{file_base}/base-user.cfg')
    monkeypatch.setattr(builtins, 'open', bad_open)

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'user-config')
    assert config.config.get('sls', 'user-config') == 'user.cfg'

    assert not config.config.has_option('sls', 'extra')


def test_reload_config_local(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'local_config', configparser.ConfigParser())
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


def test_reload_config_local_missing(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'local_config', configparser.ConfigParser())
    monkeypatch.setattr(config, 'local_config_path', None)
    monkeypatch.setattr(config, 'base_config_path', f'{file_base}/base-local.cfg')

    config.reload_config()

    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'local-config')
    assert config.config.get('sls', 'local-config') == 'local.cfg'
    assert config.local_config_path == 'local.cfg'

    assert not config.config.has_option('sls', 'local')
    assert not config.local_config.has_section('sls')


def test_reload_config_local_inaccessible(monkeypatch):
    fake_path = 'local.cfg'
    hit = False

    real_open = open

    def bad_open(path, *args, **kwargs):
        nonlocal hit
        if path == fake_path:
            hit = True
            raise PermissionError
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'local_config', configparser.ConfigParser())
    monkeypatch.setattr(config, 'local_config_path', None)
    monkeypatch.setattr(config, 'base_config_path', f'{file_base}/base-local.cfg')
    monkeypatch.setattr(builtins, 'open', bad_open)
    monkeypatch.chdir(file_base)

    config.reload_config()

    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'local-config')
    assert config.config.get('sls', 'local-config') == 'local.cfg'
    assert config.local_config_path == 'local.cfg'

    assert not config.config.has_option('sls', 'local')
    assert not config.local_config.has_section('sls')


def test_reload_config_interpolation(monkeypatch):
    monkeypatch.setattr(config, 'config', None)
    monkeypatch.setattr(config, 'base_config_path', f'{file_base}/interpolation.cfg')

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'base')
    assert config.config.has_section('section')
    assert config.config.has_option('section', 'gordon')
    assert config.config.get('sls', 'base') == '/fake'
    assert config.config.get('sls', 'subdir') == '/fake/dir'
    assert config.config.get('section', 'gordon') == '/fake/freeman'


def test_migrate_key(monkeypatch):
    custom_config = CustomConfig(monkeypatch)
    custom_config.user.add_section('test')
    custom_config.user.set('test', 'subject', 'Chel')
    custom_config.write()

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'user-config')
    assert config.config.get('sls', 'user-config') == custom_config.user_file.name
    assert config.config.has_option('sls', 'local-config')
    assert config.config.get('sls', 'local-config') == custom_config.local_file.name

    assert config.config.has_section('test')
    assert config.config.get('test', 'subject') == 'Chel'
    assert not config.local_config.has_section('test')

    assert config.migrate_key('test', 'subject')
    config.reload_config()

    assert not config.config.has_section('test') or not config.config.has_option('test', 'subject')
    assert config.local_config.has_section('test')
    assert config.local_config.get('test', 'subject') == 'Chel'


def test_migrate_key_missing_key(monkeypatch):
    custom_config = CustomConfig(monkeypatch)
    custom_config.user.add_section('test')
    custom_config.write()

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'user-config')
    assert config.config.get('sls', 'user-config') == custom_config.user_file.name
    assert config.config.has_option('sls', 'local-config')
    assert config.config.get('sls', 'local-config') == custom_config.local_file.name

    assert config.config.has_section('test')
    assert not config.config.has_option('test', 'subject')
    assert not config.local_config.has_section('test')

    assert not config.migrate_key('test', 'subject')
    config.reload_config()

    assert not config.config.has_section('test') or not config.config.has_option('test', 'subject')
    assert not config.local_config.has_section('test')


def test_migrate_key_missing_section(monkeypatch):
    custom_config = CustomConfig(monkeypatch)
    custom_config.write()

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'user-config')
    assert config.config.get('sls', 'user-config') == custom_config.user_file.name
    assert config.config.has_option('sls', 'local-config')
    assert config.config.get('sls', 'local-config') == custom_config.local_file.name

    assert not config.config.has_section('test')
    assert not config.local_config.has_section('test')

    assert not config.migrate_key('test', 'subject')
    config.reload_config()

    assert not config.config.has_section('test')
    assert not config.local_config.has_section('test')


def test_migrate_key_duplicate(monkeypatch):
    custom_config = CustomConfig(monkeypatch)
    custom_config.user.add_section('test')
    custom_config.user.set('test', 'subject', 'Chel')
    custom_config.local.add_section('test')
    custom_config.local.set('test', 'subject', 'Wheatley')
    custom_config.write()

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.has_option('sls', 'user-config')
    assert config.config.get('sls', 'user-config') == custom_config.user_file.name
    assert config.config.has_option('sls', 'local-config')
    assert config.config.get('sls', 'local-config') == custom_config.local_file.name

    assert config.config.has_section('test')
    assert config.config.get('test', 'subject') == 'Chel'
    assert config.local_config.has_section('test')
    assert config.local_config.get('test', 'subject') == 'Wheatley'

    assert not config.migrate_key('test', 'subject')
    config.reload_config()

    assert config.config.has_section('test')
    assert config.config.get('test', 'subject') == 'Chel'
    assert config.local_config.has_section('test')
    assert config.local_config.get('test', 'subject') == 'Wheatley'


def test_upgrade(monkeypatch):
    monkeypatch.setattr(sls.helpers, 'list_helpers', lambda: ['test'])
    custom_config = CustomConfig(monkeypatch)
    custom_config.user.add_section('sls')
    custom_config.user.set('sls', 'enable', 'on')
    custom_config.user.add_section('steam')
    custom_config.user.set('steam', 'account_id', '12345')
    custom_config.user.set('steam', 'account_name', 'my_luggage')
    custom_config.user.set('steam', 'deck_serial', 'druidia')
    custom_config.user.set('steam', 'egs', 'does not exist')
    custom_config.user.add_section('helpers.test')
    custom_config.user.set('helpers.test', 'enable', 'on')
    custom_config.user.set('helpers.test', 'foo', 'bar')
    custom_config.write()

    config.reload_config()
    assert config.config.has_section('sls')
    assert config.config.get('sls', 'enable') == 'on'
    assert config.config.has_section('steam')
    assert config.config.get('steam', 'account_id') == '12345'
    assert config.config.get('steam', 'account_name') == 'my_luggage'
    assert config.config.get('steam', 'deck_serial') == 'druidia'
    assert config.config.get('steam', 'egs') == 'does not exist'
    assert config.config.has_section('helpers.test')
    assert config.config.get('helpers.test', 'enable') == 'on'
    assert config.config.get('helpers.test', 'foo') == 'bar'

    assert not config.local_config.has_section('sls')
    assert not config.local_config.has_section('steam')
    assert not config.local_config.has_section('helpers.test')

    config.upgrade()

    assert config.config.has_section('sls')
    assert not config.config.has_option('sls', 'enable')
    assert config.config.has_section('steam')
    assert not config.config.has_option('steam', 'account_id')
    assert not config.config.has_option('steam', 'account_name')
    assert not config.config.has_option('steam', 'deck_serial')
    assert config.config.get('steam', 'egs') == 'does not exist'
    assert config.config.has_section('helpers.test')
    assert not config.config.has_option('helpers.test', 'enable')
    assert config.config.get('helpers.test', 'foo') == 'bar'

    assert config.local_config.has_section('sls')
    assert config.local_config.get('sls', 'enable') == 'on'
    assert config.local_config.has_section('steam')
    assert config.local_config.get('steam', 'account_id') == '12345'
    assert config.local_config.get('steam', 'account_name') == 'my_luggage'
    assert config.local_config.get('steam', 'deck_serial') == 'druidia'
    assert not config.local_config.has_option('steam', 'egs')
    assert config.local_config.has_section('helpers.test')
    assert config.local_config.get('helpers.test', 'enable') == 'on'
    assert not config.local_config.has_option('helpers.test', 'foo')
