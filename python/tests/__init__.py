import io
import requests

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


def fake_request(status_code):
    def ret(*args, **kwargs):
        r = requests.Response()
        r.status_code = status_code
        return r
    return ret


def fake_response(body):
    def ret(*args, **kwargs):
        r = requests.Response()
        r.status_code = 200
        r._content = body.encode()
        return r
    return ret
