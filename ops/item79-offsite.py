#!/usr/bin/env python3
"""Pull encrypted Item79 backups into an isolated, encrypted local restic repository."""
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile

CONFIG = Path('/etc/item79-ops/offsite.json')
ROOT = Path('/var/lib/item79-offsite')
ID = r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def atomic_json(path, data):
    require(not path.is_symlink(), 'Unexpected state symlink')
    pending = path.with_name(path.name + '.pending')
    with pending.open('w', encoding='utf-8') as out:
        json.dump(data, out); out.flush(); os.fsync(out.fileno())
    pending.chmod(0o600)
    os.replace(pending, path)


def extract_verified(archive, target, expected_manifest):
    target.mkdir(mode=0o700)
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            name = PurePosixPath(member.name)
            require(not name.is_absolute() and '..' not in name.parts and member.isfile(), 'Unsafe snapshot archive member')
            file = target.joinpath(*name.parts)
            require(file.resolve().is_relative_to(target.resolve()), 'Unsafe archive path')
            file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            require(not file.exists(), 'Duplicate archive file')
            with tar.extractfile(member) as source, file.open('xb') as out:
                shutil.copyfileobj(source, out, length=1024 * 1024)
            file.chmod(0o600)
    manifest_file = target / 'manifest.json'
    require(digest(manifest_file) == expected_manifest, 'Manifest transport mismatch')
    manifest = json.loads(manifest_file.read_text())
    validate_payload(target, manifest)
    return manifest


def validate_payload(target, manifest):
    require(not any(p.is_symlink() for p in target.rglob('*')), 'Unexpected restored symlink')
    actual = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    require(actual == set(manifest['files']) | {'manifest.json'}, 'Restored file list mismatch')
    for name, item in manifest['files'].items():
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts, 'Invalid manifest path')
        file = target.joinpath(*path.parts)
        require(file.stat().st_size == item['bytes'] and digest(file) == item['sha256'], 'Restored file checksum mismatch')


def restic(config, arguments, cwd=None):
    env = dict(os.environ, RESTIC_PASSWORD_FILE=config['passwordFile'], XDG_CACHE_HOME=str(ROOT / 'cache'))
    result = subprocess.run(['restic', '--repo', str(ROOT / 'repository')] + arguments, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0, 'Encrypted restic operation failed')
    return result.stdout


def pull(config):
    require(ROOT.resolve() == ROOT and ROOT.is_dir(), 'Unexpected offsite root')
    ssh = ['ssh', '-i', config['sourceKey'], '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + config['sourceKnownHosts'], '-o', 'ConnectTimeout=15', config['sourceUser'] + '@' + config['sourceHost']]
    result = subprocess.run(ssh + ['status'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0, 'Source backup receipt unavailable')
    receipt = json.loads(result.stdout)
    require(re.fullmatch(ID, receipt['snapshot']) is not None and re.fullmatch('[a-f0-9]{64}', receipt['sha256']) is not None, 'Invalid source receipt')
    created = datetime.datetime.fromisoformat(receipt['createdAt'])
    age = datetime.datetime.now(datetime.timezone.utc) - created
    require(-datetime.timedelta(minutes=5) < age < datetime.timedelta(hours=30), 'Source backup timestamp is stale or in the future')
    saved = ROOT / 'receipts' / (receipt['snapshot'] + '.json')
    if saved.exists():
        prior = json.loads(saved.read_text())
        require(prior['cipherSha256'] == receipt['sha256'], 'Previously saved snapshot changed')
        snapshots = json.loads(restic(config, ['snapshots', '--json', prior['resticSnapshot']]))
        require(len(snapshots) == 1 and snapshots[0]['id'].startswith(prior['resticSnapshot']), 'Previously verified Restic snapshot is missing')
        atomic_json(ROOT / 'latest.json', prior)
        return {'event': 'offsite_already_verified', 'snapshot': receipt['snapshot']}
    require(shutil.disk_usage(ROOT).free > receipt['bytes'] * 4 + 4 * 1024**3, 'Insufficient offsite disk headroom')
    staging_parent = ROOT / 'staging'
    staging_parent.mkdir(mode=0o700, exist_ok=True)
    # This temporary directory is exclusively generated transport/restore scratch.
    with tempfile.TemporaryDirectory(prefix=receipt['snapshot'] + '-', dir=staging_parent) as temporary:
        work = Path(temporary)
        cipher = work / 'snapshot.age'
        with cipher.open('wb') as out:
            result = subprocess.run(ssh + ['fetch ' + receipt['snapshot']], stdout=out, stderr=subprocess.PIPE)
        cipher.chmod(0o600)
        require(result.returncode == 0 and cipher.stat().st_size == receipt['bytes'] and digest(cipher) == receipt['sha256'], 'Encrypted offsite transfer mismatch')
        archive = work / 'snapshot.tar.gz'
        result = subprocess.run(['age', '--decrypt', '-i', config['ageIdentity'], '-o', str(archive), str(cipher)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        require(result.returncode == 0, 'Snapshot authentication/decryption failed')
        archive.chmod(0o600)
        payload = work / 'payload'
        manifest = extract_verified(archive, payload, receipt['manifestSha256'])
        output = restic(config, ['backup', '--json', '--host', 'contabo-item79', '--tag', 'item79', '--tag', receipt['snapshot'], str(payload)])
        summaries = [json.loads(line) for line in output.splitlines() if line]
        snapshot = next((item['snapshot_id'] for item in summaries if item.get('message_type') == 'summary'), None)
        require(snapshot and re.fullmatch('[a-f0-9]{8,64}', snapshot), 'Missing encrypted snapshot ID')
        restored = work / 'restore'
        restic(config, ['restore', snapshot, '--target', str(restored)])
        manifests = list(restored.rglob('manifest.json'))
        require(len(manifests) == 1 and digest(manifests[0]) == receipt['manifestSha256'], 'Restic restore manifest mismatch')
        validate_payload(manifests[0].parent, manifest)
        proof = {'snapshot': receipt['snapshot'], 'resticSnapshot': snapshot, 'cipherSha256': receipt['sha256'], 'manifestSha256': receipt['manifestSha256'], 'fileCount': len(manifest['files']), 'verifiedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'allFilesRestoredAndHashed': True}
        saved.parent.mkdir(mode=0o700, exist_ok=True)
        atomic_json(saved, proof)
        atomic_json(ROOT / 'latest.json', proof)
        return {'event': 'offsite_backup_verified', **proof}


def main():
    import signal
    def terminate(signum, _frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    os.umask(0o077)
    import fcntl
    with (ROOT / '.pull.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = json.loads(CONFIG.read_text())
        import sys
        if sys.argv[1:] == ['--check-repository']:
            restic(config, ['check', '--read-data'])
            proof = {'event': 'offsite_repository_check_passed', 'verifiedAt': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            atomic_json(ROOT / 'integrity.json', proof)
            print(json.dumps(proof))
        else:
            print(json.dumps(pull(config)))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        import traceback
        failure = ROOT / '.last-error.log'
        failure.write_text(traceback.format_exc())
        failure.chmod(0o600)
        print(json.dumps({'event': 'offsite_backup_failed', 'errorType': type(error).__name__}))
        raise SystemExit(1)
