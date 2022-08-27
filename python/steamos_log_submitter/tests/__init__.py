import io

def open_shim(text):
    def open_fake(*args):
        return io.StringIO(text)
    return open_fake


def open_shim_cb(cb):
    def open_fake(fname, *args):
        text = cb(fname)
        if text is None:
            raise FileNotFoundError
        return io.StringIO(text)
    return open_fake
