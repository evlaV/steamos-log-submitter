import os
import pytest
import tempfile
import time
import steamos_log_submitter.cli as cli
import steamos_log_submitter.config as config
from . import drop_root, mock_config  # NOQA: F401


def test_status(capsys, mock_config):
    mock_config.add_section('sls')

    mock_config.set('sls', 'enable', 'off')
    cli.main(['status'])
    assert capsys.readouterr().out.strip().endswith('disabled')

    mock_config.set('sls', 'enable', 'on')
    cli.main(['status'])
    assert capsys.readouterr().out.strip().endswith('enabled')

    mock_config.set('sls', 'enable', 'foo')
    cli.main(['status'])
    assert capsys.readouterr().out.strip().endswith('disabled')


def test_enable(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    assert cli.set_enabled(True)
    with open(user_config.name) as f:
        assert f.read() == '[sls]\nenable = on\n\n'

    assert cli.set_enabled(False)
    with open(user_config.name) as f:
        assert f.read() == '[sls]\nenable = off\n\n'


def test_enable2(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    cli.main(['enable'])
    with open(user_config.name) as f:
        assert f.read() == '[sls]\nenable = on\n\n'

    cli.main(['disable'])
    with open(user_config.name) as f:
        assert f.read() == '[sls]\nenable = off\n\n'


def test_disable(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    assert cli.set_enabled(False)
    with open(user_config.name) as f:
        assert f.read() == '[sls]\nenable = off\n\n'

    assert cli.set_enabled(True)
    with open(user_config.name) as f:
        assert f.read() == '[sls]\nenable = on\n\n'


def test_disable2(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    cli.main(['disable'])
    with open(user_config.name) as f:
        assert f.read() == '[sls]\nenable = off\n\n'

    cli.main(['enable'])
    with open(user_config.name) as f:
        assert f.read() == '[sls]\nenable = on\n\n'


def test_no_config(monkeypatch):
    monkeypatch.setattr(config, 'user_config_path', None)
    assert not cli.set_enabled(True)


def test_create_file(monkeypatch):
    prefix = int((time.time() % 1) * 0x400000)
    user_config = f'{prefix:06x}.cfg'
    assert not os.access(user_config, os.F_OK)
    monkeypatch.setattr(config, 'user_config_path', user_config)
    try:
        assert cli.set_enabled(True)
        with open(user_config) as f:
            assert f.read() == '[sls]\nenable = on\n\n'
    finally:
        os.unlink(user_config)


def test_update_file(monkeypatch):
    prefix = int((time.time() % 1) * 0x400000)
    user_config = f'{prefix:06x}.cfg'
    with open(user_config, 'w') as f:
        f.write('[test]\nempty = 0\n\n')
    monkeypatch.setattr(config, 'user_config_path', user_config)
    try:
        assert cli.set_enabled(True)
        with open(user_config) as f:
            assert f.read() == '[test]\nempty = 0\n\n[sls]\nenable = on\n\n'
    finally:
        os.unlink(user_config)


def test_clobber_file(monkeypatch):
    prefix = int((time.time() % 1) * 0x400000)
    user_config = f'{prefix:06x}.cfg'
    with open(user_config, 'w') as f:
        f.write('=invalid=')
    monkeypatch.setattr(config, 'user_config_path', user_config)
    try:
        assert not cli.set_enabled(True)
        with open(user_config) as f:
            assert f.read() == '=invalid='
    finally:
        os.unlink(user_config)


def test_inaccessible_config(drop_root, monkeypatch):
    if os.access('/', os.W_OK):
        pytest.skip('Directory is writable, are we running as root?')
    monkeypatch.setattr(config, 'user_config_path', '/doesnotexist')
    assert not cli.set_enabled(True)


def test_set_steam_key_account_name(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    assert cli.set_steam_info('account-name', 'gaben')
    with open(user_config.name) as f:
        assert f.read() == '[steam]\naccount_name = gaben\n\n'


def test_set_steam_key_account_name2(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    cli.main(['set-steam-info', 'account-name', 'gaben'])
    with open(user_config.name) as f:
        assert f.read() == '[steam]\naccount_name = gaben\n\n'


def test_set_steam_key_account_id(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    assert cli.set_steam_info('account-id', '42')
    with open(user_config.name) as f:
        assert f.read() == '[steam]\naccount_id = 42\n\n'


def test_set_steam_key_account_id2(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    cli.main(['set-steam-info', 'account-id', '42'])
    with open(user_config.name) as f:
        assert f.read() == '[steam]\naccount_id = 42\n\n'


def test_set_steam_key_account_id_invalid(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    assert not cli.set_steam_info('account-id', 'gaben')
    with open(user_config.name) as f:
        assert f.read() == ''


def test_set_steam_key_account_id_invalid2(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    cli.main(['set-steam-info', 'account-id', 'gaben'])
    with open(user_config.name) as f:
        assert f.read() == ''


def test_set_steam_key_deck_serial(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    assert cli.set_steam_info('deck-serial', 'AAAA0000')
    with open(user_config.name) as f:
        assert f.read() == '[steam]\ndeck_serial = AAAA0000\n\n'


def test_set_steam_key_deck_serial2(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    cli.main(['set-steam-info', 'deck-serial', 'AAAA0000'])
    with open(user_config.name) as f:
        assert f.read() == '[steam]\ndeck_serial = AAAA0000\n\n'


def test_set_steam_key_invalid(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    assert not cli.set_steam_info('malicious_key', 'Breen')
    with open(user_config.name) as f:
        assert f.read() == ''


def test_set_steam_key_invalid2(monkeypatch):
    user_config = tempfile.NamedTemporaryFile(suffix='.cfg', dir=os.getcwd())
    monkeypatch.setattr(config, 'user_config_path', user_config.name)
    try:
        cli.main(['set-steam-info', 'malicious_key', 'Breen'])
        assert False
    except SystemExit:
        pass
    with open(user_config.name) as f:
        assert f.read() == ''
