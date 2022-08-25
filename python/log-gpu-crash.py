#!/usr/bin/python
import os
import time
import steamos_log_submitter as sls

os.makedirs(f'{sls.pending}/gpu-crash', mode=0o755, exist_ok=True)
ts = time.time_ns()

with open(f'{sls.pending}/gpu-crash/{ts}.log', 'w') as f:
	pid = None
	for key, val in os.environ.items():
		if key in ('PWD', '_'):
			continue
		if key == 'PID':
			pid = int(val)
		print(f'{key}={val}', file=f)
	if pid:
		appid = sls.get_appid(pid)
		print(f'APPID={appid}', file=f)

sls.trigger()
