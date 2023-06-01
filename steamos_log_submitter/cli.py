import argparse
import configparser
import sys
import steamos_log_submitter as sls
import steamos_log_submitter.config as config


def set_enabled(enable) -> bool:
    if not config.user_config_path:
        print("No user configuration file path found")
        return False
    user_config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    try:
        with open(config.user_config_path) as f:
            user_config.read_file(f, source=config.user_config_path)
    except FileNotFoundError:
        pass
    except OSError:
        print("Couldn't open configuration file")
        return False
    except configparser.Error:
        print("Invalid config file. Please fix manually.")
        return False

    if not user_config.has_section('sls'):
        user_config.add_section('sls')
    user_config.set('sls', 'enable', 'on' if enable else 'off')

    try:
        with open(config.user_config_path, 'w') as f:
            user_config.write(f)
    except OSError:
        print("Couldn't open configuration file")
        return False
    return True


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        prog='steamos-log-submitter',
        description='SteamOS log collectin and submission tool')
    parser.add_argument('command', choices=('status', 'enable', 'disable'))
    args = parser.parse_args(args)
    if args.command == 'status':
        print('Log submission is currently ' + ('enabled' if sls.base_config['enable'] == 'on' else 'disabled'))
    if args.command == 'enable':
        set_enabled(True)
    if args.command == 'disable':
        set_enabled(False)


if __name__ == '__main__':  # pragma: no cover
    main()
