# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import configparser
import logging
import pwd

uid = 1000
base_config_path = '/usr/lib/steamos-log-submitter/base.cfg'
user_home = pwd.getpwuid(uid).pw_dir
user_config_path = f'{user_home}/.steam/root/config/steamos-log-submitter.cfg'

local_config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
local_config_path = None


class ConfigSection:
    def __init__(self, name, *, defaults={}):
        self.name = name
        self._defaults = defaults or {}

    def __getitem__(self, name):
        if local_config.has_section(self.name) and local_config.has_option(self.name, name):
            return local_config.get(self.name, name)
        if config.has_section(self.name) and config.has_option(self.name, name):
            return config.get(self.name, name)
        if name in self._defaults:
            return self._defaults[name]
        raise KeyError(name)

    def __setitem__(self, name, value):
        if not local_config.has_section(self.name):
            local_config.add_section(self.name)
        local_config.set(self.name, name, str(value))

    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default


def get_config(mod, defaults=None) -> ConfigSection:
    if mod == 'steamos_log_submitter':
        return ConfigSection('sls', defaults=defaults)
    if not mod.startswith('steamos_log_submitter.'):
        raise KeyError(mod)
    return ConfigSection(mod.split('.', 1)[1], defaults=defaults)


def reload_config():
    global config
    global local_config_path
    config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())

    try:
        with open(base_config_path) as f:
            config.read_file(f, source=base_config_path)
    except FileNotFoundError:
        logging.warning('No config file found')

    try:
        with open(user_config_path) as f:
            config.read_file(f, source=user_config_path)
    except FileNotFoundError:
        pass

    if config.has_section('sls') and config.has_option('sls', 'local-config'):
        local_config_path = config.get('sls', 'local-config')
        if local_config_path is not None:
            try:
                with open(local_config_path) as f:
                    local_config.read_file(f, source=local_config_path)
            except FileNotFoundError:
                pass
    else:
        local_config_path = None


def write_config():
    if local_config_path is None:
        raise FileNotFoundError
    with open(local_config_path, 'w') as f:
        local_config.write(f)


reload_config()

# vim:ts=4:sw=4:et
