import argparse
import configparser
import sys
import steamos_log_submitter as sls
import steamos_log_submitter.config as config
from typing import Optional


def load_user_config() -> Optional[configparser.ConfigParser]:
    if not config.user_config_path:
        print("No user configuration file path found")
        return None
    user_config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    try:
        with open(config.user_config_path) as f:
            user_config.read_file(f, source=config.user_config_path)
    except FileNotFoundError:
        pass
    except OSError:
        print("Couldn't open configuration file")
        return None
    except configparser.Error:
        print("Invalid config file. Please fix manually.")
        return None
    return user_config


def save_user_config(user_config: configparser.ConfigParser) -> bool:
    try:
        with open(config.user_config_path, 'w') as f:
            user_config.write(f)
    except OSError:
        print("Couldn't open configuration file")
        return False
    return True


def set_enabled(enable) -> bool:
    user_config = load_user_config()
    if not user_config:
        return False

    if not user_config.has_section('sls'):
        user_config.add_section('sls')
    user_config.set('sls', 'enable', 'on' if enable else 'off')

    return save_user_config(user_config)


def do_status(args):
    print('Log submission is currently ' + ('enabled' if sls.base_config['enable'] == 'on' else 'disabled'))


def set_steam_info(key, value) -> bool:
    if key not in ('account-name', 'account-id', 'deck-serial'):
        print(f"'{key}' is not a valid Steam info key")
        return False
    if key == 'account-id':
        try:
            int(value)
        except ValueError:
            print('Account ID must be numeric')
            return False

    user_config = load_user_config()
    if not user_config:
        return False

    if not user_config.has_section('steam'):
        user_config.add_section('steam')
    user_config.set('steam', key.replace('-', '_'), value)

    return save_user_config(user_config)


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        prog='steamos-log-submitter',
        description='SteamOS log collectin and submission tool')
    subparsers = parser.add_subparsers(required=True)

    status = subparsers.add_parser('status')
    status.set_defaults(func=do_status)

    enable = subparsers.add_parser('enable')
    enable.set_defaults(func=lambda _: set_enabled(True))

    disable = subparsers.add_parser('disable')
    disable.set_defaults(func=lambda _: set_enabled(False))

    set_steam = subparsers.add_parser('set-steam-info')
    set_steam.add_argument('key', choices=('account-name', 'account-id', 'deck-serial'))
    set_steam.add_argument('value', type=str)
    set_steam.set_defaults(func=lambda args: set_steam_info(args.key, args.value))

    args = parser.parse_args(args)

    args.func(args)


if __name__ == '__main__':  # pragma: no cover
    main()
