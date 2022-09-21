# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import configparser
import logging

CONFIG_PATH = '/etc/steamos-log-submitter.cfg'

CONFIG = configparser.ConfigParser(default_section='sls', interpolation=None)

class ConfigSection:
    def __init__(self, *, data={}, defaults={}):
        self._data = data or {}
        self._defaults = defaults or {}

    def __getitem__(self, name):
        if name in self._data:
            return self._data[name]
        if name in self._defaults:
            return self._defaults[name]
        raise KeyError(name)

    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default


def get_config(mod, defaults=None):
    if mod == 'steamos_log_submitter':
        return ConfigSection(data=CONFIG['sls'], defaults=defaults)
    if not mod.startswith('steamos_log_submitter.'):
        raise KeyError(mod)
    try:
        return ConfigSection(data=CONFIG[mod.split('.', 1)[1]], defaults=defaults)
    except KeyError:
        return ConfigSection(defaults=defaults)


try:  # pragma: no cover
    with open(CONFIG_PATH) as f:
        CONFIG.read_file(f, source=CONFIG_PATH)
except FileNotFoundError:  # pragma: no cover
    logging.warning('No config file found')

# vim:ts=4:sw=4:et
