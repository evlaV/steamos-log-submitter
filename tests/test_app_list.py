# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2024 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import sqlite3
import httpx
import pytest
import steamos_log_submitter as sls
from . import count_hits, data_directory  # NOQA: F401


def test_get_app_name_no_db(data_directory):
    assert sls.util.get_app_name(666) is None


def test_get_app_name(data_directory):
    db = sqlite3.connect(f'{sls.data.data_root}/applist.sqlite3')
    cursor = db.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS applist (
        appid INTEGER,
        name TEXT,
        PRIMARY KEY (appid)
    )''')
    cursor.execute('INSERT INTO applist (appid, name) VALUES (69, "Half-Life 3"), (420, "Ricochet 2")')
    cursor.close()
    db.commit()

    assert sls.util.get_app_name(69) == 'Half-Life 3'
    assert sls.util.get_app_name(420) == 'Ricochet 2'
    assert sls.util.get_app_name(666) is None


@pytest.mark.asyncio
async def test_create_app_list(data_directory, monkeypatch):
    applist = '''{
        "applist": {
            "apps": [
                {
                    "appid": 69,
                    "name": "Half-Life 3"
                },
                {
                    "appid": 420,
                    "name": "Ricochet 2"
                }
            ]
        }
    }'''

    async def fake_response(self, url, headers, *args, **kwargs):
        return httpx.Response(200, content=applist.encode())

    monkeypatch.setattr(httpx.AsyncClient, 'get', fake_response)

    assert await sls.util.update_app_list()
    assert sls.util.get_app_name(69) == 'Half-Life 3'
    assert sls.util.get_app_name(420) == 'Ricochet 2'
    assert sls.util.get_app_name(666) is None


@pytest.mark.asyncio
async def test_update_app_list(count_hits, data_directory, monkeypatch):
    applist = [
        '''{
            "applist": {
                "apps": [
                    {
                        "appid": 69,
                        "name": "Half-Life 3"
                    },
                    {
                        "appid": 420,
                        "name": "Ricochet 2"
                    }
                ]
            }
        }''',
        '''{
            "applist": {
                "apps": [
                    {
                        "appid": 69,
                        "name": "Left 4 Dead 3"
                    },
                    {
                        "appid": 420,
                        "name": "Alien Swarm 2"
                    }
                ]
            }
        }''',
    ]

    async def fake_response(self, url, headers, *args, **kwargs):
        count_hits()
        return httpx.Response(200, content=applist[count_hits.hits - 1].encode())

    monkeypatch.setattr(httpx.AsyncClient, 'get', fake_response)

    assert await sls.util.update_app_list()
    assert sls.util.get_app_name(69) == 'Half-Life 3'
    assert sls.util.get_app_name(420) == 'Ricochet 2'
    assert sls.util.get_app_name(666) is None

    assert await sls.util.update_app_list()
    assert sls.util.get_app_name(69) == 'Left 4 Dead 3'
    assert sls.util.get_app_name(420) == 'Alien Swarm 2'
    assert sls.util.get_app_name(666) is None
