import json
import pwd
import steamos_log_submitter.cli as cli
import steamos_log_submitter.helpers as helpers
import steamos_log_submitter.steam as steam
from . import always_raise
from . import drop_root, fake_socket, mock_config, sync_client  # NOQA: F401


def test_status(capsys, mock_config, sync_client):
    mock_config.add_section('sls')
    sync_client.start()

    mock_config.set('sls', 'enable', 'off')
    cli.main(['status'])
    assert capsys.readouterr().out.strip().endswith('disabled')

    mock_config.set('sls', 'enable', 'on')
    cli.main(['status'])
    assert capsys.readouterr().out.strip().endswith('enabled')

    mock_config.set('sls', 'enable', 'foo')
    cli.main(['status'])
    assert capsys.readouterr().out.strip().endswith('disabled')


def test_status_json(capsys, mock_config, sync_client):
    mock_config.add_section('sls')
    sync_client.start()

    mock_config.set('sls', 'enable', 'off')
    cli.main(['status', '-J'])
    assert json.loads(capsys.readouterr().out.strip())['enabled'] is False

    mock_config.set('sls', 'enable', 'on')
    cli.main(['status', '-J'])
    assert json.loads(capsys.readouterr().out.strip())['enabled'] is True

    mock_config.set('sls', 'enable', 'foo')
    cli.main(['status', '-J'])
    assert json.loads(capsys.readouterr().out.strip())['enabled'] is False


def test_list(capsys, monkeypatch, sync_client):
    monkeypatch.setattr(helpers, 'list_helpers', lambda: ['test'])
    sync_client.start()
    cli.main(['list'])
    assert capsys.readouterr().out.strip() == 'test'


def test_log_level(capsys, mock_config, monkeypatch, sync_client):
    mock_config.add_section('logging')
    mock_config.set('logging', 'level', 'ERROR')
    sync_client.start()
    cli.main(['log-level'])
    assert capsys.readouterr().out.strip() == 'ERROR'


def test_set_log_level(mock_config, monkeypatch, sync_client):
    mock_config.add_section('logging')
    sync_client.start()
    cli.main(['log-level', 'error'])
    assert mock_config.get('logging', 'level') == 'ERROR'


def test_invalid_log_level(capsys, mock_config, monkeypatch, sync_client):
    mock_config.add_section('logging')
    sync_client.start()
    cli.main(['log-level', 'foo'])
    assert capsys.readouterr().err.strip() == 'Please specify a valid log level'


def test_enable(sync_client):
    sync_client.start()
    assert sync_client.status() is False

    cli.main(['enable'])
    assert sync_client.status() is True


def test_disable(sync_client):
    sync_client.start()
    sync_client.enable()
    assert sync_client.status() is True

    cli.main(['disable'])
    assert sync_client.status() is False


def test_enable_helper(mock_config, monkeypatch, sync_client):
    monkeypatch.setattr(helpers, 'list_helpers', lambda: ['test'])
    sync_client.start()
    sync_client.disable_helpers(['test'])
    assert mock_config.has_section('helpers.test')
    assert mock_config.get('helpers.test', 'enable') == 'off'

    cli.main(['enable-helper', 'test'])
    assert mock_config.get('helpers.test', 'enable') == 'on'


def test_disable_helper(mock_config, monkeypatch, sync_client):
    monkeypatch.setattr(helpers, 'list_helpers', lambda: ['test'])
    sync_client.start()
    sync_client.enable_helpers(['test'])
    assert mock_config.has_section('helpers.test')
    assert mock_config.get('helpers.test', 'enable') == 'on'

    cli.main(['disable-helper', 'test'])
    assert mock_config.get('helpers.test', 'enable') == 'off'


def test_enable_helpers(mock_config, monkeypatch, sync_client):
    monkeypatch.setattr(helpers, 'list_helpers', lambda: ['test', 'test2'])
    sync_client.start()
    sync_client.disable_helpers(['test', 'test2'])
    assert mock_config.has_section('helpers.test')
    assert mock_config.get('helpers.test', 'enable') == 'off'
    assert mock_config.has_section('helpers.test2')
    assert mock_config.get('helpers.test2', 'enable') == 'off'
    cli.main(['enable-helper', 'test', 'test2'])
    assert mock_config.get('helpers.test', 'enable') == 'on'
    assert mock_config.get('helpers.test2', 'enable') == 'on'


def test_enable_invalid_helper(capsys, mock_config, monkeypatch, sync_client):
    monkeypatch.setattr(helpers, 'list_helpers', lambda: ['test'])
    sync_client.start()
    cli.main(['enable-helper', 'test2'])
    assert not mock_config.has_section('helpers.test2')
    assert capsys.readouterr().err.strip() == 'Invalid helpers: test2'


def test_disable_helpers(mock_config, monkeypatch, sync_client):
    monkeypatch.setattr(helpers, 'list_helpers', lambda: ['test', 'test2'])
    sync_client.start()
    sync_client.enable_helpers(['test', 'test2'])
    assert mock_config.has_section('helpers.test')
    assert mock_config.get('helpers.test', 'enable') == 'on'
    assert mock_config.has_section('helpers.test2')
    assert mock_config.get('helpers.test2', 'enable') == 'on'
    cli.main(['disable-helper', 'test', 'test2'])
    assert mock_config.get('helpers.test', 'enable') == 'off'
    assert mock_config.get('helpers.test2', 'enable') == 'off'


def test_set_steam_key_account_name(mock_config, monkeypatch, sync_client):
    monkeypatch.setattr(pwd, 'getpwuid', always_raise(OSError))
    sync_client.start()
    cli.main(['set-steam-info', 'account-name', 'gaben'])
    assert mock_config.has_section('steam')
    assert mock_config.get('steam', 'account_name') == 'gaben'
    assert steam.get_steam_account_name() == 'gaben'


def test_set_steam_key_account_id(mock_config, monkeypatch, sync_client):
    monkeypatch.setattr(pwd, 'getpwuid', always_raise(OSError))
    sync_client.start()
    cli.main(['set-steam-info', 'account-id', '42'])
    assert mock_config.has_section('steam')
    assert mock_config.get('steam', 'account_id') == '42'
    assert steam.get_steam_account_id() == 42


def test_set_steam_key_account_id_invalid(mock_config, monkeypatch, sync_client):
    monkeypatch.setattr(pwd, 'getpwuid', always_raise(OSError))
    sync_client.start()
    assert not mock_config.has_section('steam')
    cli.main(['set-steam-info', 'account-id', 'gaben'])
    assert not mock_config.has_section('steam')
    assert steam.get_steam_account_id() is None


def test_set_steam_key_deck_serial(mock_config, monkeypatch, sync_client):
    monkeypatch.setattr(pwd, 'getpwuid', always_raise(OSError))
    sync_client.start()
    cli.main(['set-steam-info', 'deck-serial', 'AAAA0000'])
    assert mock_config.has_section('steam')
    assert mock_config.get('steam', 'deck_serial') == 'AAAA0000'
    assert steam.get_deck_serial() == 'AAAA0000'


def test_set_steam_key_invalid(mock_config, sync_client):
    sync_client.start()
    assert not mock_config.has_section('steam')
    try:
        cli.main(['set-steam-info', 'malicious_key', 'Breen'])
        assert False
    except SystemExit:
        pass
    assert not mock_config.has_section('steam')
