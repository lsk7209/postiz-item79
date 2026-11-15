#!/usr/bin/env python3
"""Daily PC coordinator. Fail closed; no original/project/backup tree deletion."""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

ROOT = Path('E:/codex-build/postiz-item79/video-cleanup')
GATE_SHA256 = 'e76d8c50b4978df965c7245c40ae8d1cd96e0bebe6e2abffc17431d7280cdc58'
CONTABO = ['ssh', '-i', str(ROOT / 'keys/contabo-reader'), '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15', '-o', 'UserKnownHostsFile=D:/server-contabo/connection-20261028/known_hosts', 'item79-cleanup-reader@13.140.77.84']
OVH = ['ssh', '-i', str(ROOT / 'keys/ovh-verifier'), '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15', '-o', 'UserKnownHostsFile=D:/server-ovhcloud/OVH-OtherPC-Start-20261028/known_hosts.ovh', 'item79-cleanup-verifier@51.79.206.71']
SERVER = r'''
import base64,json,subprocess
from pathlib import Path
root=Path('/opt/postiz-center-20261112')
assert __import__('socket').gethostname()=='vmi3690013'
lock=(root/'.video-cleanup.lock').open('a'); __import__('fcntl').flock(lock,__import__('fcntl').LOCK_EX|__import__('fcntl').LOCK_NB)
state=json.loads((root/'web-release.json').read_text()); slot=state['activeSlot']; assert slot in ('blue','green')
source_bytes=Path('/usr/local/lib/item79/item79-video-gate.cjs').read_bytes()
assert __import__('hashlib').sha256(source_bytes).hexdigest()=='GATE_PIN','Unreviewed server gate'
source=source_bytes.decode()
code=source+'\nmodule.exports.main(JSON.parse(Buffer.from("INPUT","base64").toString())).then(r=>console.log(JSON.stringify(r))).catch(()=>{console.error("Video gate failed closed");process.exitCode=1});'
result=subprocess.run(['docker','exec','-w','/app','postiz-item79-web-'+slot+'-web-1','node','-e',code],capture_output=True,timeout=180)
assert result.returncode==0,'Server gate failed closed'
print(result.stdout.decode())
'''
VERIFY = r'''
import datetime,hashlib,importlib.util,json,os,subprocess
from pathlib import Path
assert __import__('socket').gethostname()=='vps-ce781f0f'
spec=importlib.util.spec_from_file_location('offsite','/usr/local/lib/item79/item79-offsite.py'); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
q=json.loads(__import__('base64').b64decode('INPUT')); path=q['path']; assert path.startswith('/uploads/') and '..' not in path.split('/')
config=json.loads(m.CONFIG.read_text()); latest=json.loads((m.ROOT/'latest.json').read_text())
now=datetime.datetime.now(datetime.timezone.utc)
age=now-datetime.datetime.fromisoformat(latest['verifiedAt'])
assert latest['allFilesRestoredAndHashed'] and datetime.timedelta(0)<=age<datetime.timedelta(hours=30),'Stale backup'
if q.get('recovery'):
 source_id=q['recovery']['sourceSnapshot']; assert __import__('re').fullmatch(m.ID,source_id)
 saved=json.loads((m.ROOT/'receipts'/(source_id+'.json')).read_text())
 assert saved['allFilesRestoredAndHashed'] and saved['resticSnapshot']==q['recovery']['snapshot']
 latest=saved
snapshot=latest['resticSnapshot']
nodes=[json.loads(line) for line in m.restic(config,['ls','--json',snapshot]).splitlines() if line]
manifests=[n['path'] for n in nodes if n.get('type')=='file' and n.get('name')=='manifest.json']; assert len(manifests)==1
manifest_bytes=m.restic(config,['dump',snapshot,manifests[0]])
assert hashlib.sha256(manifest_bytes).hexdigest()==latest['manifestSha256']
manifest=json.loads(manifest_bytes); key=path.lstrip('/'); item=manifest['files'][key]
assert item['sha256']==q['sha256'] and item['bytes']==q['bytes'],'Backup content differs'
restore_path=str(Path(manifests[0]).parent/key)
env=dict(os.environ,RESTIC_PASSWORD_FILE=config['passwordFile'],XDG_CACHE_HOME=str(m.ROOT/'cache'))
with __import__('tempfile').TemporaryFile() as errors:
 with subprocess.Popen(['restic','--repo',str(m.ROOT/'repository'),'dump',snapshot,restore_path],env=env,stdout=subprocess.PIPE,stderr=errors) as child:
  digest=hashlib.sha256();size=0
  while chunk:=child.stdout.read(1048576):digest.update(chunk);size+=len(chunk)
  assert child.wait()==0
assert digest.hexdigest()==q['sha256'] and size==q['bytes'],'Recovery readback mismatch'
print(json.dumps({'restoredAndHashed':True,'sha256':digest.hexdigest(),'bytes':size,'snapshot':snapshot,'sourceSnapshot':latest['snapshot'],'manifestSha256':latest['manifestSha256'],'verifiedAt':now.isoformat()}))
'''
EXPORT = r'''
import socket,subprocess
assert socket.gethostname()=='vmi3690013'
result=subprocess.run(['python3','/usr/local/lib/item79/item79-server-video-cleanup.py','--export'],capture_output=True,timeout=210)
assert result.returncode==0,'Server receipts unavailable'
print(result.stdout.decode())
'''

def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError('State symlink')
    temp = path.with_suffix('.pending')
    with temp.open('w', encoding='utf-8') as out:
        json.dump(value, out, indent=2); out.flush(); os.fsync(out.fileno())
    os.replace(temp, path)


def remote(ssh, source, data):
    if ssh == CONTABO:
        if source == EXPORT:
            data = {'mode': 'export'}
        elif source != SERVER or data.get('mode') not in ['receipt', 'local-check']:
            raise RuntimeError('PC transport forbids server mutation')
    elif ssh != OVH or source != VERIFY:
        raise RuntimeError('Unknown restricted transport')
    result = subprocess.run(ssh + ['verify' if ssh == OVH else 'read'], input=json.dumps(data).encode(), capture_output=True, timeout=240)
    if result.returncode:
        raise RuntimeError('Remote verification failed closed')
    return json.loads(result.stdout)


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def verify_installation():
    config = json.loads((ROOT / 'installation.json').read_text(encoding='utf-8-sig'))
    if (config['gateSha256'] != GATE_SHA256 or config['runnerSha256'] != digest(Path(__file__)) or
            config['localMapSha256'] != digest(ROOT / 'local-map.json')):
        raise RuntimeError('Installed cleanup code or enrollment changed')


def update_observed(prior, public_ids, now):
    # A private/missing/disconnected observation resets the seven-day window.
    return {key: prior.get(key, now) for key in public_ids}


def local_candidates(mapping, candidate):
    same = [entry for entry in mapping if entry['sha256'] == candidate['sha256']]
    # Any additional native or Postiz reservation protects that local byte identity.
    if any(entry.get('postId') not in candidate['postIds'] for entry in same):
        return []
    return list({entry['resolvedPath']: entry for entry in same if entry.get('deleteEligible') is True}.values())


def delete_local(entry, candidate):
    path = Path(entry['resolvedPath'])
    if entry.get('localAssetId') != hashlib.sha256((str(path) + ':' + candidate['sha256']).encode()).hexdigest():
        raise RuntimeError('Local enrollment changed')
    allowed = [Path('D:/youtube-money/motion-engine/workspace/out').resolve(), Path('E:/shorts_factory_data/storage').resolve()]
    # Only individually enrolled canonical final MP4s; junction aliases are never unlinked.
    if not path.is_absolute() or str(path.resolve()).casefold() != str(path).casefold() or not any(path.is_relative_to(r) for r in allowed):
        raise RuntimeError('Local path outside enrolled roots')
    if not path.exists():
        raise RuntimeError('Missing local file requires reconciliation')
    stat = path.lstat()
    if not path.is_file() or path.is_symlink() or getattr(stat, 'st_nlink', 1) != 1 or path.suffix.lower() != '.mp4':
        raise RuntimeError('Unsafe local file')
    exclusive_remove(path, candidate['sha256'], candidate['bytes'])
    return {'path': str(path), 'state': 'REMOVED', 'bytes': stat.st_size}


def clean_local(mapping, candidate, intent, journal):
    completed = intent.setdefault('local', [])
    for entry in local_candidates(mapping, candidate):
        if any(item.get('localAssetId') == entry['localAssetId'] for item in completed):
            continue
        if intent.get('localPending') == entry['localAssetId'] and not Path(entry['resolvedPath']).exists():
            # Acknowledge absence after a durable intent without claiming who removed bytes.
            completed.append({'path': entry['resolvedPath'], 'state': 'REMOVED_UNCONFIRMED', 'localAssetId': entry['localAssetId'],
                              'bytes': 0, 'expectedBytes': candidate['bytes']})
            intent.pop('localPending', None); atomic(journal, intent)
            continue
        intent['localPending'] = entry['localAssetId']; atomic(journal, intent)
        result = delete_local(entry, candidate) | {'localAssetId': entry['localAssetId']}
        completed.append(result); intent.pop('localPending', None); atomic(journal, intent)
    return completed


def exclusive_remove(path, sha256, size):
    """Windows exclusive handle: no publisher/renderer may have the file open."""
    import ctypes
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    handle = create(str(path), 0x80000000 | 0x10000, 0, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), 'Exclusive local file unavailable')
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    with os.fdopen(fd, 'rb') as source:
        if os.fstat(source.fileno()).st_size != size or hashlib.file_digest(source, 'sha256').hexdigest() != sha256:
            raise RuntimeError('Local bytes changed')
        disposition = wintypes.BOOL(True)
        setter = kernel.SetFileInformationByHandle
        setter.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        setter.restype = wintypes.BOOL
        if not setter(handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
            raise OSError(ctypes.get_last_error(), 'Local deletion refused')


def run(apply=False):
    ROOT.mkdir(parents=True, exist_ok=True)
    if Path(__file__).name == 'runner.py':
        verify_installation()
    # OS-held byte lock survives exceptions and is released by process termination.
    import msvcrt
    with (ROOT / 'run.lock').open('a+b') as lock:
        lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        return execute_local_only(apply)


def execute_local_only(apply):
    """PC task consumes acknowledged server removals; it never requests server unlink."""
    report = {'startedAt': utc(), 'mode': 'LOCAL_ONLY_APPLY' if apply else 'LOCAL_ONLY_AUDIT',
              'state': 'RUNNING', 'serverRemoved': [], 'localRemoved': [], 'failures': [], 'eligibleCount': 0,
              'protectedCounts': {}, 'localUnconfirmed': []}
    atomic(ROOT / 'latest.json', report)
    exported = remote(CONTABO, EXPORT, {})
    observed = exported['observed']
    mapping = json.loads((ROOT / 'local-map.json').read_text())
    for server_intent in exported['receipts']:
        candidate = server_intent['candidate']
        if not local_candidates(mapping, candidate):
            continue
        operation = server_intent['operationId']
        if not __import__('re').fullmatch('[a-f0-9]{32}', operation):
            raise RuntimeError('Invalid server operation identity')
        journal = ROOT / 'pc-receipts' / (operation + '.json')
        selected = local_candidates(mapping, candidate)
        intent = json.loads(journal.read_text()) if journal.exists() else {
            'state': 'LOCAL_PENDING', 'operationId': operation, 'candidate': candidate, 'recovery': server_intent['recovery'],
            'selectedLocal': selected}
        if intent['candidate'] != candidate or intent['recovery'] != server_intent['recovery']:
            raise RuntimeError('Server receipt changed')
        if intent['state'] in ['COMPLETED', 'COMPLETED_WITH_UNCONFIRMED']:
            continue
        report['eligibleCount'] += 1
        try:
            ack = remote(CONTABO, SERVER, {'mode': 'receipt', 'operationId': operation})
            if (ack.get('state') != 'REMOVED' or ack.get('operationId') != operation or
                    ack.get('expected') != candidate or ack.get('recovery') != server_intent['recovery']):
                raise RuntimeError('Server removal not acknowledged')
            proof = remote(OVH, VERIFY, candidate | {'recovery': intent['recovery']})
            if proof.get('restoredAndHashed') is not True or proof.get('sha256') != candidate['sha256'] or proof.get('bytes') != candidate['bytes']:
                raise RuntimeError('Recovery content differs')
            check = remote(CONTABO, SERVER, {'mode': 'local-check', 'operationId': operation})
            if not check.get('permitted'):
                raise RuntimeError('References or public status changed')
            if apply:
                atomic(journal, intent)
                local = clean_local(intent['selectedLocal'], candidate, intent, journal)
                report['localRemoved'].extend(item for item in local if item['state'] == 'REMOVED')
                report['localUnconfirmed'].extend(item for item in local if item['state'] == 'REMOVED_UNCONFIRMED')
                intent.update(state='COMPLETED_WITH_UNCONFIRMED' if any(item['state'] == 'REMOVED_UNCONFIRMED' for item in local) else 'COMPLETED', verifiedAt=utc()); atomic(journal, intent)
        except Exception as error:
            report['failures'].append({'sha256': candidate['sha256'], 'errorType': type(error).__name__})
    report.update(state='COMPLETED' if not report['failures'] else 'PARTIAL_REQUIRES_RECONCILIATION', completedAt=utc())
    atomic(ROOT / 'latest.json', report)
    atomic(ROOT / 'runs' / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json'), report)
    return {key: report[key] for key in ['state', 'eligibleCount', 'protectedCounts']} | {'serverRemoved': 0, 'localRemoved': len(report['localRemoved'])}


def execute(apply):
    state_path = ROOT / 'observed.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    report = {'startedAt': utc(), 'mode': 'APPLY' if apply else 'AUDIT', 'state': 'RUNNING', 'serverRemoved': [], 'localRemoved': [], 'failures': []}
    atomic(ROOT / 'latest.json', report)
    current = remote(CONTABO, SERVER, {'mode': 'inspect', 'observed': state})
    observed = update_observed(state, current['publicIds'], current['capturedAt'])
    atomic(state_path, observed)
    report['protectedCounts'] = current['protectedCounts']
    report['eligibleCount'] = len(current['candidates'])
    mapping = json.loads((ROOT / 'local-map.json').read_text())
    # Resume only confirmed server removals. Unacknowledged intents remain held for reconciliation.
    for journal in sorted((ROOT / 'receipts').glob('*.json')):
        intent = json.loads(journal.read_text())
        if intent.get('state') == 'VERIFIED_INTENT' and apply:
            try:
                ack = remote(CONTABO, SERVER, {'mode': 'receipt', 'operationId': intent['operationId']})
                if ack['state'] == 'REMOVED' and ack.get('operationId') == intent['operationId'] and ack.get('expected') == intent['candidate'] and ack.get('recovery') == intent['recovery']:
                    intent['state'] = 'SERVER_REMOVED'; atomic(journal, intent)
                elif ack['state'] in ['NOT_STARTED', 'RESTORED']:
                    intent['state'] = 'ABORTED'; atomic(journal, intent)
                else:
                    raise RuntimeError('Ambiguous prior removal')
            except Exception as error:
                report['failures'].append({'sha256': intent['candidate']['sha256'], 'errorType': type(error).__name__})
        if intent.get('state') != 'SERVER_REMOVED' or not apply:
            continue
        candidate = intent['candidate']
        try:
            proof = remote(OVH, VERIFY, candidate | {'recovery': intent['recovery']})
            check = remote(CONTABO, SERVER, {'mode': 'local-check', 'observed': observed, 'expected': candidate})
            if not check.get('permitted'):
                raise RuntimeError('References changed')
            local = clean_local(mapping, candidate, intent, journal)
            report['localRemoved'].extend(local)
            intent.update(state='COMPLETED', local=local, recovery=proof)
            atomic(journal, intent)
        except Exception as error:
            report['failures'].append({'sha256': candidate['sha256'], 'errorType': type(error).__name__})
    for candidate in current['candidates']:
        try:
            proof = remote(OVH, VERIFY, candidate)
            intent = {'state': 'VERIFIED_INTENT', 'candidate': candidate, 'recovery': proof, 'operationId': uuid.uuid4().hex, 'at': utc()}
            if not apply:
                continue
            journal = ROOT / 'receipts' / (candidate['sha256'] + '-' + hashlib.sha256(candidate['path'].encode()).hexdigest()[:16] + '.json')
            if journal.exists():
                prior = json.loads(journal.read_text())
                if prior.get('state') not in ['COMPLETED', 'ABORTED']:
                    raise RuntimeError('Prior ambiguous removal requires reconciliation')
            atomic(journal, intent)
            removed = remote(CONTABO, SERVER, {'mode': 'remove', 'observed': observed, 'expected': candidate, 'recovery': proof, 'operationId': intent['operationId']})
            # If SSH result is ambiguous, no local deletion. Preserve the intent for reconciliation.
            if removed != {'removed': candidate['path'], 'operationId': intent['operationId'], **candidate, 'recovery': proof}:
                raise RuntimeError('Ambiguous server removal')
            report['serverRemoved'].append(removed)
            intent['state'] = 'SERVER_REMOVED'; atomic(journal, intent)
            check = remote(CONTABO, SERVER, {'mode': 'local-check', 'observed': observed, 'expected': candidate})
            if not check.get('permitted'):
                raise RuntimeError('References changed before local deletion')
            report['localRemoved'].extend(clean_local(mapping, candidate, intent, journal))
            intent['state'] = 'COMPLETED'; atomic(journal, intent)
        except Exception as error:
            report['failures'].append({'sha256': candidate['sha256'], 'errorType': type(error).__name__})
    report['state'] = 'COMPLETED' if not report['failures'] else 'PARTIAL_REQUIRES_RECONCILIATION'
    report['completedAt'] = utc()
    atomic(ROOT / 'latest.json', report)
    atomic(ROOT / 'runs' / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json'), report)
    return {key: report[key] for key in ['state', 'eligibleCount', 'protectedCounts']} | {'serverRemoved': len(report['serverRemoved']), 'localRemoved': len(report['localRemoved'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--local-only', action='store_true', help='PC cleanup is always local-only; server runs independently')
    arguments = parser.parse_args()
    try:
        summary = run(arguments.apply)
        print(json.dumps(summary))
        if summary['state'] != 'COMPLETED':
            sys.exit(1)
    except Exception as error:
        if ROOT.exists():
            atomic(ROOT / 'latest-failure.json', {'state': 'FAILED_CLOSED', 'at': utc(), 'errorType': type(error).__name__})
        print(json.dumps({'state': 'FAILED_CLOSED', 'errorType': type(error).__name__}))
        sys.exit(1)
