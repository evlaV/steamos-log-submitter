import os
import requests
import steamos_log_submitter as sls

start_url = "https://api.steampowered.com/ICrashReportService/StartCrashUpload/v1"
finish_url = "https://api.steampowered.com/ICrashReportService/FinishCrashUpload/v1"

def upload(product, *, build=None, version, info, dump=None, filename=None) -> bool:
    account = sls.util.get_steam_account_id()

    info = dict(info)
    info.update({
        'steam_id': account or 'null',
        'have_dump_file': 1 if dump else 0,
        'product': product,
        'build': build or 'null',
        'version': version,
        'platform': 'linux',
        'format': 'json'
    })
    if dump:
        info['dump_file_size'] = os.stat(dump).st_size

    start = requests.post(start_url, data=info)
    if start.status_code // 100 != 2:
        return False

    response = start.json()['response']
    headers = {pair.name: pair.value for pair in response['headers']['pairs']}
    if not filename:
        filename = os.path.basename(dump)

    put = requests.put(response['url'], headers=headers, files={filename: open(dump, 'rb')})
    if put.status_code // 100 != 2:
        return False

    finish = requests.post(finish_url, data={'gid': response['gid']})
    if finish.status_code // 100 != 2:
        return False

    return True
