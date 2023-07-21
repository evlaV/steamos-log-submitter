import argparse
import json
import sys
import steamos_log_submitter as sls
import steamos_log_submitter.client
from collections.abc import Sequence


class ClientWrapper:
    def __enter__(self):
        try:
            client = sls.client.Client()
            return client
        except FileNotFoundError:
            print("Can't connect to daemon. Is service running?", file=sys.stderr)
            return None

    def __exit__(self, exc_type, exc_value, traceback):
        return not exc_type


def set_enabled(enable: bool):
    with ClientWrapper() as client:
        if not client:
            return
        client.enable(enable)


def set_helper_enabled(helpers: list[str], enable: bool):
    with ClientWrapper() as client:
        if not client:
            return
        valid_helpers = set(sls.helpers.list_helpers())
        our_helpers = set(helpers)
        invalid_helpers = our_helpers - valid_helpers
        if invalid_helpers:
            print('Invalid helpers:', ', '.join(invalid_helpers), file=sys.stderr)
            helpers = list(our_helpers & valid_helpers)
        if enable:
            client.enable_helpers(helpers)
        else:
            client.disable_helpers(helpers)


def do_status(args: argparse.Namespace) -> None:
    with ClientWrapper() as client:
        if not client:
            return
        if not args.json:
            print('Log submission is currently ' + ('enabled' if sls.base_config['enable'] == 'on' else 'disabled'))
        else:
            blob = {'enabled': sls.base_config['enable'] == 'on'}
            print(json.dumps(blob))


def do_list(args: argparse.Namespace) -> None:
    for helper in sorted(sls.helpers.list_helpers()):
        print(helper)


def do_log_level(args: argparse.Namespace) -> None:
    with ClientWrapper() as client:
        if not client:
            return
        if args.level is None:
            print(client.log_level())
        elif sls.logging.valid_level(args.level):
            client.set_log_level(args.level)
        else:
            print('Please specify a valid log level', file=sys.stderr)


def set_steam_info(key: str, value: str) -> bool:
    if key == 'account-id':
        try:
            int(value)
        except ValueError:
            print('Account ID must be numeric', file=sys.stderr)
            return False

    with ClientWrapper() as client:
        if not client:
            return
        client.set_steam_info(key.replace('-', '_'), value)


def do_trigger(args: argparse.Namespace) -> None:
    with ClientWrapper() as client:
        if not client:
            return
        client.trigger(args.wait)


def main(args: Sequence[str] = sys.argv[1:]) -> None:
    parser = argparse.ArgumentParser(
        prog='steamos-log-submitter',
        description='SteamOS log collection and submission tool')
    subparsers = parser.add_subparsers(required=True, metavar='command')

    status = subparsers.add_parser('status',
                                   description='Display the current status of the log collection service.',
                                   help='Current status')
    status.add_argument('--json', '-J', action='store_true', help='Output results as JSON')
    status.set_defaults(func=do_status)

    list_cmd = subparsers.add_parser('list',
                                     description='''List all available helper modules. Each helper
                                                    module handles one or more types of logs that have
                                                    a common method of collection and submission.''',
                                     help='List helper modules')
    list_cmd.set_defaults(func=do_list)

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

    trigger = subparsers.add_parser('trigger',
                                    description='Trigger an immediate log collection and submission',
                                    help='Trigger collection/submission')
    trigger.add_argument('--wait', action='store_true', help='Wait until complete')
    trigger.set_defaults(func=do_trigger)

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
