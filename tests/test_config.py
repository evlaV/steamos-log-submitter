import steamos_log_submitter.config as config

def test_section_get_no_val_no_default():
    section = config.ConfigSection()
    try:
        foo = section['nothing']
        assert False
    except KeyError:
        pass


def test_section_get_val_no_default():
    section = config.ConfigSection(data={'nothing': True})
    try:
        assert section['nothing']
    except KeyError:
        assert False


def test_section_get_no_val_default():
    section = config.ConfigSection(defaults={'nothing': True})
    try:
        assert section['nothing']
    except KeyError:
        assert False



def test_section_get_val_default():
    section = config.ConfigSection(data={'nothing': True}, defaults={'nothing': False})
    try:
        assert section['nothing']
    except KeyError:
        assert False


def test_get_config_out_of_scope():
    try:
        section = config.get_config('builtins')
        assert False
    except KeyError:
        pass


def test_get_config_no_section(monkeypatch):
    monkeypatch.setattr(config, 'CONFIG', {})
    section = config.get_config('steamos_log_submitter.foo')
    assert section
    assert not section._data
    assert not section._defaults

# vim:ts=4:sw=4:et
