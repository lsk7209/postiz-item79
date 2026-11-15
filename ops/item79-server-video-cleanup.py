#!/usr/bin/env python3
"""PC-independent Contabo coordinator; preserves the reviewed video gate."""
import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

spec = importlib.util.spec_from_file_location('cleanup_common', Path(__file__).with_name('item79-video-cleanup.py'))
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
ROOT = Path('/var/lib/item79-video-cleanup')
CONFIG = Path('/etc/item79-ops/video-cleanup.json')


def gate(data):
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    code = common.SERVER.replace('INPUT', encoded).replace('GATE_PIN', common.GATE_SHA256)
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, timeout=210)
    if result.returncode:
        raise RuntimeError('Server video gate failed closed')
    return json.loads(result.stdout)


def verify(candidate):
    config = json.loads(CONFIG.read_text())
    ssh = ['ssh', '-i', config['verifierKey'], '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
           '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + config['verifierKnownHosts'],
           '-o', 'ConnectTimeout=15', '-o', 'ClearAllForwardings=yes',
           'item79-cleanup-verifier@51.79.206.71', 'verify']
    result = subprocess.run(ssh, input=json.dumps(candidate).encode(), capture_output=True, timeout=240)
    if result.returncode:
        raise RuntimeError('Independent recovery verification failed closed')
    proof = json.loads(result.stdout)
    if proof.get('restoredAndHashed') is not True or proof.get('sha256') != candidate['sha256'] or proof.get('bytes') != candidate['bytes']:
        raise RuntimeError('Independent recovery bytes differ')
    return proof


def ack_matches(ack, intent):
    return (ack.get('state') == 'REMOVED' and ack.get('operationId') == intent['operationId'] and
            ack.get('expected') == intent['candidate'] and ack.get('recovery') == intent['recovery'])


def execute(apply):
    observed_path = ROOT / 'observed.json'
    observed = json.loads(observed_path.read_text()) if observed_path.exists() else {}
    report = {'startedAt': common.utc(), 'mode': 'SERVER_APPLY' if apply else 'SERVER_AUDIT',
              'state': 'RUNNING', 'serverRemoved': [], 'failures': []}
    common.atomic(ROOT / 'latest.json', report)
    current = gate({'mode': 'inspect', 'observed': observed})
    observed = common.update_observed(observed, current['publicIds'], current['capturedAt'])
    common.atomic(observed_path, observed)
    report.update(eligibleCount=len(current['candidates']), protectedCounts=current['protectedCounts'])
    reconciled_paths = set()
    if apply:
        for journal in sorted((ROOT / 'receipts').glob('*.json')):
            intent = json.loads(journal.read_text())
            if intent['state'] != 'VERIFIED_INTENT':
                continue
            try:
                ack = gate({'mode': 'receipt', 'operationId': intent['operationId']})
                if ack_matches(ack, intent):
                    intent.update(state='COMPLETED', removalAcknowledgedAt=common.utc()); common.atomic(journal, intent)
                    reconciled_paths.add(intent['candidate']['path'])
                elif ack['state'] in ['NOT_STARTED', 'RESTORED']:
                    intent['state'] = 'ABORTED'; common.atomic(journal, intent)
                else:
                    raise RuntimeError('Ambiguous earlier server removal')
            except Exception as error:
                report['failures'].append({'sha256': intent['candidate']['sha256'], 'reason': str(error)[:120]})
    for candidate in current['candidates']:
        if candidate['path'] in reconciled_paths:
            continue
        try:
            proof = verify(candidate)
            if not apply:
                continue
            journal = ROOT / 'receipts' / (candidate['sha256'] + '-' + common.hashlib.sha256(candidate['path'].encode()).hexdigest()[:16] + '.json')
            if journal.exists() and json.loads(journal.read_text())['state'] not in ['COMPLETED', 'ABORTED']:
                raise RuntimeError('Earlier ambiguous intent remains held')
            intent = {'schemaVersion': 1, 'state': 'VERIFIED_INTENT', 'operationId': uuid.uuid4().hex, 'candidate': candidate,
                      'recovery': proof, 'gateSha256': common.GATE_SHA256, 'observed': observed, 'at': common.utc()}
            common.atomic(journal, intent)
            removed = gate({'mode': 'remove', 'observed': observed, 'expected': candidate,
                            'recovery': proof, 'operationId': intent['operationId']})
            expected = {'removed': candidate['path'], 'operationId': intent['operationId'], **candidate, 'recovery': proof}
            if removed != expected:
                raise RuntimeError('Ambiguous server removal acknowledgement')
            intent.update(state='COMPLETED', removedAt=common.utc()); common.atomic(journal, intent)
            report['serverRemoved'].append(removed)
        except Exception as error:
            report['failures'].append({'sha256': candidate['sha256'], 'reason': str(error)[:120]})
    report.update(state='COMPLETED' if not report['failures'] else 'PARTIAL_REQUIRES_RECONCILIATION', completedAt=common.utc())
    common.atomic(ROOT / 'latest.json', report)
    common.atomic(ROOT / 'runs' / (report['startedAt'].replace(':', '').replace('+', '_') + '.json'), report)
    return report


def export():
    receipts = [json.loads(p.read_text()) for p in sorted((ROOT / 'receipts').glob('*.json'))]
    return {'observed': json.loads((ROOT / 'observed.json').read_text()),
            'receipts': [r for r in receipts if r['state'] == 'COMPLETED']}


def run(apply=False, exporting=False):
    import fcntl
    os.umask(0o077)
    config = json.loads(CONFIG.read_text())
    for name in ['item79-server-video-cleanup.py', 'item79-video-cleanup.py']:
        if common.hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != config['sourceHashes'][name]:
            raise RuntimeError('Unreviewed server cleanup code')
    if ROOT.resolve() != ROOT or not ROOT.is_dir() or ROOT.is_symlink():
        raise RuntimeError('Unsafe server cleanup root')
    with (ROOT / 'run.lock').open('a') as lock, Path('/opt/postiz-center-20261112/.deploy.lock').open('a') as release_lock:
        fcntl.flock(lock, (fcntl.LOCK_SH if exporting else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        fcntl.flock(release_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return export() if exporting else execute(apply)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true')
    modes.add_argument('--export', action='store_true', dest='exporting')
    args = parser.parse_args()
    try:
        result = run(args.apply, args.exporting)
        if args.exporting:
            print(json.dumps(result))
        else:
            print(json.dumps({'state': result['state'], 'eligibleCount': result['eligibleCount'],
                              'serverRemoved': len(result['serverRemoved']), 'failures': len(result['failures'])}))
            if result['state'] != 'COMPLETED':
                sys.exit(1)
    except Exception as error:
        common.atomic(ROOT / 'latest-failure.json', {'state': 'FAILED_CLOSED', 'at': common.utc(), 'errorType': type(error).__name__})
        print(json.dumps({'state': 'FAILED_CLOSED', 'errorType': type(error).__name__}))
        sys.exit(1)
