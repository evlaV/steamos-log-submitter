import requests
import steamos_log_submitter.crash as crash
from . import fake_request

def test_bad_start(monkeypatch):
    monkeypatch.setattr(requests, 'post', fake_request(400))
    assert not crash.upload('holo', version=0, info={})
