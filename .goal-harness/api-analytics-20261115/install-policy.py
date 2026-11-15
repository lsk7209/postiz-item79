"""Install only the reviewed web-source exception; retain prior root policy."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
from diagnose import SSH

REMOTE = r'''
import ast,base64,hashlib,json,os,tempfile,time
from pathlib import Path
packet=json.load(__import__('sys').stdin)
target=Path('/usr/local/lib/item79/item79_release_policy.py')
assert target.is_file() and not target.is_symlink()
before=target.read_bytes()
assert hashlib.sha256(before).hexdigest()==packet['previousSha256'], 'Installed policy differs; stop for review'
content=base64.b64decode(packet['content'])
assert hashlib.sha256(content).hexdigest()==packet['sha256']
ast.parse(content)
backup=target.with_name('item79_release_policy.pre-analytics-'+str(time.time_ns())+'.py.bak')
with backup.open('xb') as out: out.write(before)
backup.chmod(0o600)
fd,pending=tempfile.mkstemp(prefix='.analytics-policy-',dir=target.parent)
with os.fdopen(fd,'wb') as out:
 out.write(content);out.flush();os.fsync(out.fileno())
os.chmod(pending,0o644)
os.replace(pending,target)
print(json.dumps({'installed':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'backup':str(backup)}))
'''
if __name__ == '__main__':
    code = Path('ops/item79_release_policy.py').read_bytes()
    old = subprocess.check_output(['git', 'show', 'HEAD:ops/item79_release_policy.py'])
    packet = {'previousSha256': hashlib.sha256(old).hexdigest(), 'sha256': hashlib.sha256(code).hexdigest(), 'content': base64.b64encode(code).decode()}
    subprocess.run(SSH + ['sudo -n python3 -c ' + shlex.quote(REMOTE)], input=json.dumps(packet), text=True, check=True)
