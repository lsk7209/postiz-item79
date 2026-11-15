"""Inspect only the current release process tree; suppress command arguments."""
import shlex
import subprocess
from diagnose import SSH
REMOTE = r'''
import json,subprocess
from pathlib import Path
roots=subprocess.run(['pgrep','-f','[c]ontabo-deploy.py'],stdout=subprocess.PIPE,text=True).stdout.split()
processes={}
for path in Path('/proc').iterdir():
 if not path.name.isdigit():continue
 try:
  stat=(path/'stat').read_text().split(') ',1)[1].split()
  args=(path/'cmdline').read_bytes().decode(errors='replace').split('\0')
  processes[int(path.name)]={'parent':int(stat[1]),'program':Path(args[0]).name,'args':args}
 except (OSError,IndexError):pass
selected={int(pid) for pid in roots}
while True:
 updated=selected|{pid for pid,p in processes.items() if p['parent'] in selected}
 if updated==selected:break
 selected=updated
for pid in sorted(selected):
 if pid not in processes:continue
 p=processes[pid];args=p.pop('args');joined=' '.join(args)
 hints=[name for name in ['pull','run','exec','pg_dump','pg_restore','up'] if name in args]
 if 'prisma migrate diff' in joined:hints.append('schema-diff')
 print(json.dumps({'pid':pid,**p,'stageHints':hints}))
'''
if __name__ == '__main__':
    subprocess.run(SSH+['sudo -n python3 -c '+shlex.quote(REMOTE)],check=True)
