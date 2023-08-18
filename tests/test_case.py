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


def test_snake_case_numeric():
    assert sls.util.snake_case('1') == '1'
    assert sls.util.snake_case('1b') == '1b'
    assert sls.util.snake_case('1B') == '1b'
    assert sls.util.snake_case('1bc') == '1bc'
    assert sls.util.snake_case('1bC') == '1b_c'
    assert sls.util.snake_case('1Bc') == '1bc'
    assert sls.util.snake_case('1BC') == '1bc'
    assert sls.util.snake_case('a2') == 'a2'
    assert sls.util.snake_case('A2') == 'a2'
    assert sls.util.snake_case('a2a') == 'a2a'
    assert sls.util.snake_case('a2A') == 'a2_a'
    assert sls.util.snake_case('A2a') == 'a2a'
    assert sls.util.snake_case('A2A') == 'a2a'


def test_camel_case():
    assert sls.util.camel_case('') == ''
    assert sls.util.camel_case('a') == 'A'
    assert sls.util.camel_case('ab') == 'Ab'
    assert sls.util.camel_case('ab_c') == 'AbC'
    assert sls.util.camel_case('a_bc') == 'ABc'
    assert sls.util.camel_case('a_bc_a') == 'ABcA'
    assert sls.util.camel_case('ab_c_ab') == 'AbCAb'
