#!/bin/bash
#
#  SPDX-License-Identifier: LGPL-2.1+
#
#  Copyright (c) 2022 Valve.
#  Author: Guilherme G. Piccoli <gpiccoli@igalia.com>
#
#  This is the systemd loader for the SteamOS kdump log submitter;
#  it's invoked by systemd, basically it just loads a detached
#  process and exits successfuly, in order to prevent boot hangs.

/usr/lib/steamos-log-submitter/submit-report.sh & disown
exit 0
