"""Scoped one-time deployment. Never prints/copies private server key material."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

CONTABO = ['ssh', '-i', 'C:/Users/dlatj/.ssh/im-cloud-contabo-admin', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=D:/server-contabo/connection-20261028/known_hosts', 'imadmin@13.140.77.84']
OVH = ['ssh', '-i', 'C:/Users/dlatj/.ssh/ovh_pc2_ed25519', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=D:/server-ovhcloud/OVH-OtherPC-Start-20261028/known_hosts.ovh', 'ubuntu@51.79.206.71']
LOCAL = Path('E:/codex-build/postiz-item79/video-cleanup')


def remote(ssh, code, data):
    result = subprocess.run(ssh + ['sudo -n python3 -c ' + shlex.quote(code)], input=json.dumps(data).encode(), capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError('Scoped install failed: ' + result.stderr.decode(errors='replace')[-900:])
    return json.loads(result.stdout)


COMMON = r'''
import base64,hashlib,json,os,pwd,socket,subprocess,sys
from pathlib import Path
q=json.load(sys.stdin); assert socket.gethostname()==q['host']
os.umask(0o077)
def put(p,data,mode):
 p=Path(p); assert not p.is_symlink();p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and p.read_bytes()!=data:
  backup=p.with_name(p.name+'.pre-server-native-20261115-'+hashlib.sha256(p.read_bytes()).hexdigest()[:12]);assert not backup.exists() or backup.read_bytes()==p.read_bytes();backup.write_bytes(p.read_bytes());backup.chmod(0o600)
 temp=p.with_name(p.name+'.install-pending');temp.write_bytes(data);temp.chmod(mode);os.replace(temp,p)
def account(name,home,helper,keys):
 try:
  u=pwd.getpwnam(name); assert u.pw_uid<1000 and u.pw_dir==home and u.pw_shell=='/bin/sh'
 except KeyError:
  subprocess.run(['useradd','--system','--user-group','--home-dir',home,'--shell','/bin/sh','--no-create-home',name],check=True)
 folder=Path(home);folder.mkdir(mode=0o755,exist_ok=True);assert not folder.is_symlink();folder.chmod(0o755)
 ssh=folder/'.ssh';ssh.mkdir(mode=0o755,exist_ok=True);ssh.chmod(0o755)
 lines=[]
 for key in keys:
  assert key.startswith('ssh-ed25519 ') and '\n' not in key and '"' not in key
  lines.append('restrict,command="/usr/bin/sudo -n '+helper+'" '+key)
 put(ssh/'authorized_keys',('\n'.join(lines)+'\n').encode(),0o644)
 sudo=Path('/etc/sudoers.d')/name
 put(sudo,(name+' ALL=(root) NOPASSWD: '+helper+' ""\n').encode(),0o440)
 subprocess.run(['visudo','-cf',str(sudo)],check=True,stdout=subprocess.DEVNULL)
for name,data in q.get('files',{}).items():
 assert name in ['item79-video-cleanup.py','item79-server-video-cleanup.py','item79-video-reader.py','item79-video-recovery.py']
 put('/usr/local/lib/item79/'+name,base64.b64decode(data),0o755)
'''


def files(names):
    return {name: base64.b64encode((Path('ops') / name).read_bytes()).decode() for name in names}


def main():
    if any(json.loads(p.read_text())['state'] not in ['COMPLETED', 'ABORTED'] for p in (LOCAL / 'receipts').glob('*.json')):
        raise RuntimeError('Prior PC operation requires reconciliation')
    shared = 'item79-video-cleanup.py'
    names = [shared, 'item79-server-video-cleanup.py', 'item79-video-reader.py']
    data = {'host': 'vmi3690013', 'files': files(names),
            'observed': json.loads((LOCAL / 'observed.json').read_text()),
            'readerPublicKey': (LOCAL / 'keys/contabo-reader.pub').read_text().strip(),
            'knownHosts': Path('D:/server-ovhcloud/OVH-OtherPC-Start-20261028/known_hosts.ovh').read_text(),
            'units': {name: (Path('ops') / name).read_text() for name in ['item79-video-cleanup.service', 'item79-video-cleanup.timer']}}
    server = COMMON + r'''
assert hashlib.sha256(Path('/usr/local/lib/item79/item79-video-gate.cjs').read_bytes()).hexdigest()=='e76d8c50b4978df965c7245c40ae8d1cd96e0bebe6e2abffc17431d7280cdc58'
journal=Path('/opt/postiz-center-20261112/uploads/.item79-cleanup')
if journal.exists():
 assert journal.resolve()==journal and not journal.is_symlink() and journal.stat().st_uid==0 and not journal.stat().st_mode&0o022
 assert not list(journal.glob('*.video')),'Orphan quarantine requires reconciliation'
 assert all(p.is_file() and not p.is_symlink() and p.suffix=='.json' and json.loads(p.read_text())['state'] in ['REMOVED','RESTORED'] for p in journal.iterdir())
root=Path('/var/lib/item79-video-cleanup');root.mkdir(mode=0o700,exist_ok=True);assert root.resolve()==root;root.chmod(0o700)
if not (root/'observed.json').exists():put(root/'observed.json',json.dumps(q['observed']).encode(),0o600)
key=Path('/etc/item79-ops/video-verifier')
if not key.exists():subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C','item79-contabo-verifier','-f',str(key)],check=True)
key.chmod(0o600); public=key.with_suffix('.pub').read_text().strip()
known='/etc/item79-ops/video-verifier-known-hosts';put(known,q['knownHosts'].encode(),0o600)
pins={name:hashlib.sha256(Path('/usr/local/lib/item79',name).read_bytes()).hexdigest() for name in q['files']}
put('/etc/item79-ops/video-cleanup.json',json.dumps({'verifierKey':str(key),'verifierKnownHosts':known,'sourceHashes':pins}).encode(),0o600)
put('/etc/item79-ops/video-reader-pins.json',json.dumps(pins).encode(),0o600)
account('item79-cleanup-reader','/var/lib/item79-cleanup-reader','/usr/local/lib/item79/item79-video-reader.py',[q['readerPublicKey']])
for name,text in q['units'].items():put('/etc/systemd/system/'+name,text.encode(),0o644)
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemd-analyze','verify','/etc/systemd/system/item79-video-cleanup.service','/etc/systemd/system/item79-video-cleanup.timer'],check=True,capture_output=True)
print(json.dumps({'publicKey':public,'sourceHashes':pins,'privateKeyTransferred':False,'timerEnabled':False}))
'''
    installed = remote(CONTABO, server, data)
    names = [shared, 'item79-video-recovery.py']
    data = {'host': 'vps-ce781f0f', 'files': files(names), 'publicKeys': [installed.pop('publicKey'), (LOCAL / 'keys/ovh-verifier.pub').read_text().strip()]}
    verifier = COMMON + r'''
assert Path('/var/lib/item79-offsite/latest.json').is_file()
pins={name:hashlib.sha256(Path('/usr/local/lib/item79',name).read_bytes()).hexdigest() for name in q['files']}
pins['runtimeFiles']={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['/usr/local/lib/item79/item79-offsite.py','/etc/item79-ops/offsite.json','/var/lib/item79-offsite/repository/config']}
put('/etc/item79-ops/video-recovery-pins.json',json.dumps(pins).encode(),0o600)
account('item79-cleanup-verifier','/var/lib/item79-cleanup-verifier','/usr/local/lib/item79/item79-video-recovery.py',q['publicKeys'])
print(json.dumps({'sourceHashes':pins,'forcedCommandKeys':len(q['publicKeys'])}))
'''
    offsite = remote(OVH, verifier, data)
    (LOCAL / 'server-installation.json').write_text(json.dumps({'contabo': installed, 'ovh': offsite}, indent=2), encoding='utf-8')
    print(json.dumps({'contaboInstalled': True, 'ovhVerifierInstalled': True, 'privateKeysTransferred': False, 'timerEnabled': False}))


if __name__ == '__main__':
    main()
