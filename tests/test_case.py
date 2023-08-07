# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter as sls


def test_snake_case():
    assert sls.util.snake_case('') == ''
    assert sls.util.snake_case('a') == 'a'
    assert sls.util.snake_case('ab') == 'ab'
    assert sls.util.snake_case('aB') == 'a_b'
    assert sls.util.snake_case('aBc') == 'a_bc'
    assert sls.util.snake_case('aBC') == 'a_bc'
    assert sls.util.snake_case('aBCa') == 'a_b_ca'
    assert sls.util.snake_case('AB') == 'ab'
    assert sls.util.snake_case('ABc') == 'a_bc'
    assert sls.util.snake_case('ABC') == 'abc'
    assert sls.util.snake_case('ABCa') == 'ab_ca'
    assert sls.util.snake_case('Ab') == 'ab'
    assert sls.util.snake_case('AbC') == 'ab_c'
    assert sls.util.snake_case('Abc') == 'abc'
    assert sls.util.snake_case('AbCa') == 'ab_ca'


def test_camel_case():
    assert sls.util.camel_case('') == ''
    assert sls.util.camel_case('a') == 'A'
    assert sls.util.camel_case('ab') == 'Ab'
    assert sls.util.camel_case('ab_c') == 'AbC'
    assert sls.util.camel_case('a_bc') == 'ABc'
    assert sls.util.camel_case('a_bc_a') == 'ABcA'
    assert sls.util.camel_case('ab_c_ab') == 'AbCAb'
