import argparse
import configparser
import sys
import steamos_log_submitter as sls
import steamos_log_submitter.config as config
from typing import Optional, Sequence


def load_user_config() -> Optional[configparser.ConfigParser]:
    if not config.user_config_path:
        print("No user configuration file path found", file=sys.stderr)
        return None
    user_config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    try:
        with open(config.user_config_path) as f:
            user_config.read_file(f, source=config.user_config_path)
    except FileNotFoundError:
        pass
    except OSError:
        print("Couldn't open configuration file", file=sys.stderr)
        return None
    except configparser.Error:
        print("Invalid config file. Please fix manually.", file=sys.stderr)
        return None
    return user_config


def save_user_config(user_config: configparser.ConfigParser) -> bool:
    if not config.user_config_path:
        return False
    try:
        with open(config.user_config_path, 'w') as f:
            user_config.write(f)
    except OSError:
        print("Couldn't open configuration file", file=sys.stderr)
        return False
    return True


def set_enabled(enable: bool) -> bool:
    user_config = load_user_config()
    if not user_config:
        return False

    if not user_config.has_section('sls'):
        user_config.add_section('sls')
    user_config.set('sls', 'enable', 'on' if enable else 'off')

    return save_user_config(user_config)


def set_helper_enabled(helpers: list[str], enable: bool) -> bool:
    user_config = load_user_config()
    if not user_config:
        return False

    did_anything = False
    for helper in helpers:
        if helper not in sls.helpers.list_helpers():
            print(f'Helper {helper} not found', file=sys.stderr)
            continue

        if not user_config.has_section(f'helpers.{helper}'):
            user_config.add_section(f'helpers.{helper}')
        user_config.set(f'helpers.{helper}', 'enable', 'on' if enable else 'off')
        did_anything = True

    if not did_anything:
        return False
    return save_user_config(user_config)


def do_status(args: argparse.Namespace) -> None:
    print('Log submission is currently ' + ('enabled' if sls.base_config['enable'] == 'on' else 'disabled'))


def do_list(args: argparse.Namespace) -> None:
    for helper in sorted(sls.helpers.list_helpers()):
        print(helper)


def do_log_level(args: argparse.Namespace) -> None:
    user_config = load_user_config()
    if not user_config:
        return

    if args.level is None:
        print(sls.logging.config.get('level', 'WARNING').upper())
    elif sls.logging.valid_level(args.level):
        if not user_config.has_section('logging'):
            user_config.add_section('logging')
        user_config.set('logging', 'level', args.level.upper())
        save_user_config(user_config)
    else:
        print('Please specify a valid log level', file=sys.stderr)


def set_steam_info(key: str, value: str) -> bool:
    if key not in ('account-name', 'account-id', 'deck-serial'):
        print(f"'{key}' is not a valid Steam info key", file=sys.stderr)
        return False
    if key == 'account-id':
        try:
            int(value)
        except ValueError:
            print('Account ID must be numeric', file=sys.stderr)
            return False

    user_config = load_user_config()
    if not user_config:
        return False

    if not user_config.has_section('steam'):
        user_config.add_section('steam')
    user_config.set('steam', key.replace('-', '_'), value)

    return save_user_config(user_config)


def main(args: Sequence[str] = sys.argv[1:]) -> None:
    parser = argparse.ArgumentParser(
        prog='steamos-log-submitter',
        description='SteamOS log collection and submission tool')
    subparsers = parser.add_subparsers(required=True, metavar='command')

    status = subparsers.add_parser('status',
                                   description='Display the current status of the log collection service.',
                                   help='Current status')
    status.set_defaults(func=do_status)

    status = subparsers.add_parser('list',
                                   description='''List all available helper modules. Each helper
                                                  module handles one or more types of logs that have
                                                  a common method of collection and submission.''',
                                   help='List helper modules')
    status.set_defaults(func=do_list)

    log_level = subparsers.add_parser('log-level',
                                      description='''Set or get the log level. If no argument is passed,
                                                     print the current log level, otherwise set a new
                                                     log level.''',
                                      help='Set or get the log level')
    log_level.add_argument('level', type=str, nargs='?',
                           help='''Which new log level to set. The possible levels are DEBUG, INFO,
                                   WARNING, ERROR, and CRITICAL, in order from least to most severe.''')
    log_level.set_defaults(func=do_log_level)

    enable = subparsers.add_parser('enable',
                                   description='Enable the log collection service.',
                                   help='Enable log collection')
    enable.set_defaults(func=lambda _: set_enabled(True))

    disable = subparsers.add_parser('disable',
                                    description='Disable the log collection service.',
                                    help='Disable log collection')
    disable.set_defaults(func=lambda _: set_enabled(False))

    enable_helper = subparsers.add_parser('enable-helper',
                                          description='Enable one or more specific helper modules.',
                                          help='Enable helper modules')
    enable_helper.add_argument('helper', nargs='+')
    enable_helper.set_defaults(func=lambda args: set_helper_enabled(args.helper, True))

    disable_helper = subparsers.add_parser('disable-helper',
                                           description='Enable one or more specific helper modules.',
                                           help='Disable helper modules')
    disable_helper.add_argument('helper', nargs='+')
    disable_helper.set_defaults(func=lambda args: set_helper_enabled(args.helper, False))

    set_steam = subparsers.add_parser('set-steam-info',
                                      description='''Set a value relating to the current Steam configuration.
                                                     This command should not be used directly, as any values
                                                     manually set may be changed by Steam directly.''')
    set_steam.add_argument('key', choices=('account-name', 'account-id', 'deck-serial'))
    set_steam.add_argument('value', type=str)
    set_steam.set_defaults(func=lambda args: set_steam_info(args.key, args.value))

    parsed_args = parser.parse_args(args)

    parsed_args.func(parsed_args)


if __name__ == '__main__':  # pragma: no cover
    main()
