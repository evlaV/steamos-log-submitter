# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter.helpers as helpers


# Ensure all helpers get set up in advance
for helper in helpers.list_helpers():
    helpers.create_helper(helper)
