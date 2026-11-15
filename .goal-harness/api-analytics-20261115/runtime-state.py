"""Whitelisted deployment/runtime evidence; never print container environment."""
import json
import shlex
import subprocess
from diagnose import SSH

REMOTE = r'''
import hashlib,json,subprocess
from pathlib import Path
root=Path('/opt/postiz-center-20261112')
info=json.loads(subprocess.check_output(['docker','inspect','postiz-center-app-1']))[0]
processes=json.loads(subprocess.check_output(['docker','exec','postiz-center-app-1','pm2','jlist']))
worker=next(p for p in processes if p['name']=='orchestrator')
files={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['compose.yaml','app.env','.env','wait-temporal.cjs','app-config/oauth-nginx.conf']}
print(json.dumps({'worker':{'container':info['Id'],'image':info['Config']['Image'],'startedAt':info['State']['StartedAt'],'restarts':info['RestartCount'],'pid':worker['pid'],'pm2Restarts':worker['pm2_env']['restart_time'],'status':worker['pm2_env']['status']},'protectedFileHashes':files,'release':json.loads((root/'web-release.json').read_text())}))
'''
if __name__ == '__main__':
    subprocess.run(SSH + ['sudo -n python3 -c ' + shlex.quote(REMOTE)], check=True)
