#!/usr/bin/python
import subprocess
import sys
import steamos_log_submitter as sls

P, e, u, g, s, t, c, h = sys.argv[1:]

appid = sls.util.get_appid(int(P))
breakpad = subprocess.Popen(['/usr/lib/core_handler', P, f'{sls.pending}/minidump/{e}-{P}-{appid}.dmp'], stdin=subprocess.PIPE)
systemd = subprocess.Popen(['/usr/lib/systemd/systemd-coredump', P, u, g, s, t, c, h], stdin=subprocess.PIPE)

while True:
    buffer = sys.stdin.buffer.read(4096)
    if not buffer:
        break
    try:
        breakpad.stdin.write(buffer)
    except:
        pass
    try:
        systemd.stdin.write(buffer)
    except:
        pass

try:
	breakpad.stdin.close()
except:
	pass
try:
    breakpad.wait(5)
except:
    pass

try:
	systemd.stdin.close()
except:
	pass
try:
    systemd.wait(5)
except:
    pass

sls.trigger()
