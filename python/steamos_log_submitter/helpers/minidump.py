#!/usr/bin/python
import os
import requests
import sys
import steamos_log_submitter as sls

dsn = 'http://127.0.0.1:9000/api/1/minidump/?sentry_key=887d785705d9443cb85750046df1b451'


def submit(fname : str) -> bool:
    name, ext = os.path.splitext(os.path.basename(fname))
    post = requests.post(dsn, files={'upload_file_minidump': open(fname, 'rb')})

    return post.status_code == 200


if __name__ == '__main__':  # pragma: no cover
    try:
        sys.exit(0 if submit(sys.argv[1]) else 1)
    except Exception as e:
        print(e)
        sys.exit(1)

# vim:ts=4:sw=4:et
