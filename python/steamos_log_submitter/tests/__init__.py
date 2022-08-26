import io

def open_shim(text):
    def open_fake(*args):
        return io.StringIO(text)
    return open_fake
