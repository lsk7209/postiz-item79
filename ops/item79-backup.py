#!/usr/bin/env python3
"""Create a private, integrity-checked Item79 recovery snapshot for offsite pull."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tarfile
import time
import tempfile

ROOT = Path('/opt/postiz-center-20261112')
CONFIG = Path('/etc/item79-ops/source.json')
OUTBOX = Path('/var/lib/item79-backup-export')
RESERVE = 12 * 1024**3


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_files(folder):
    require(folder.is_dir() and not folder.is_symlink(), 'Invalid snapshot source')
    entries = sorted(folder.rglob('*'))
    require(not any(p.is_symlink() for p in entries), 'Symlink in snapshot source')
    return [p for p in entries if p.is_file()]


def verify_tar(archive, manifest):
    with tarfile.open(archive, 'r:gz') as tar:
        members = {m.name: m for m in tar.getmembers() if m.isfile()}
        require(set(members) == set(manifest['files']) | {'manifest.json'}, 'Snapshot file list mismatch')
        for name, item in manifest['files'].items():
            member = members[name]
            require(member.size == item['bytes'], 'Snapshot size mismatch')
            with tar.extractfile(member) as source:
                require(hashlib.file_digest(source, 'sha256').hexdigest() == item['sha256'], 'Snapshot content mismatch')


class GuardedWriter:
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        require(shutil.disk_usage(ROOT).free > RESERVE + len(data), 'Snapshot reserve reached')
        return self.stream.write(data)

    def __getattr__(self, name):
        return getattr(self.stream, name)


def export_bounded(command, target):
    with target.open('wb') as out, tempfile.TemporaryFile() as errors:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors) as child:
            try:
                while chunk := child.stdout.read(1024 * 1024):
                    GuardedWriter(out).write(chunk)
                require(child.wait() == 0, 'Snapshot export command failed')
            except BaseException:
                child.kill(); child.wait()
                raise
    target.chmod(0o600)


def build_snapshot(config):
    require(ROOT.resolve() == ROOT and OUTBOX.resolve() == OUTBOX, 'Unexpected backup root')
    snapshot = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(4)
    parent = ROOT / 'ops-staging'
    parent.mkdir(mode=0o700, exist_ok=True)
    require(parent.resolve().parent == ROOT, 'Invalid staging parent')
    stage = parent / snapshot
    stage.mkdir(mode=0o700)
    try:
        return _build_snapshot(config, snapshot, stage)
    finally:
        # Only this invocation's generated plaintext and unfinished cipher are scratch.
        require(stage.resolve().parent == parent.resolve() and stage.name == snapshot and not stage.is_symlink(), 'Unsafe staging cleanup')
        shutil.rmtree(stage)
        partial = OUTBOX / (snapshot + '.tar.gz.age.partial')
        if partial.exists():
            require(not partial.is_symlink() and partial.resolve().parent == OUTBOX, 'Unsafe cipher scratch')
            partial.unlink()


def _build_snapshot(config, snapshot, stage):
    dc = ['docker', 'compose', '--project-directory', str(ROOT)]
    uploads = safe_files(ROOT / 'uploads')
    runtime = uploads + safe_files(ROOT / 'app-config')
    total = sum(p.stat().st_size for p in runtime)
    require(shutil.disk_usage(ROOT).free > total * 3 + RESERVE, 'Insufficient backup headroom')
    # Estimates include each database, while bounded writers enforce the reserve
    # throughout dumps, archive creation and encryption even if data grows.
    database_bytes = 0
    for service, user, database in [('database', 'postiz', 'postiz'), ('temporal-db', 'temporal', 'temporal')]:
        database_bytes += int(subprocess.check_output(dc + ['exec', '-T', service, 'psql', '-U', user, '-d', database, '-At', '-c', 'SELECT pg_database_size(current_database())']))
    require(shutil.disk_usage(ROOT).free > (total + database_bytes) * 3 + RESERVE, 'Insufficient database backup headroom')
    files = {}
    paths = {}
    for name in ['compose.yaml', 'app.env', '.env', 'wait-temporal.cjs', 'image-lock.json']:
        source = ROOT / name
        if source.is_file():
            target = stage / name
            shutil.copy2(source, target)
            target.chmod(0o600)
            paths['config/' + name] = target
    route = Path('/data/coolify/proxy/dynamic/postiz-item79.yml')
    shutil.copy2(route, stage / 'public-route.json')
    (stage / 'public-route.json').chmod(0o600)
    paths['config/public-route.json'] = stage / 'public-route.json'
    # Each pg_dump owns a consistent read transaction. Never restore production here.
    for service, user, database in [('database', 'postiz', 'postiz'), ('temporal-db', 'temporal', 'temporal')]:
        target = stage / (database + '.dump')
        export_bounded(dc + ['exec', '-T', service, 'pg_dump', '-U', user, '-d', database, '-Fc'], target)
        require(target.stat().st_size > 1000, 'Database snapshot is empty')
        paths['database/' + database + '.dump'] = target
    redis = stage / 'redis.rdb'
    export_bounded(dc + ['exec', '-T', 'redis', 'redis-cli', '--rdb', '-'], redis)
    with redis.open('rb') as source:
        require(source.read(5) == b'REDIS', 'Redis snapshot format invalid')
    paths['redis/redis.rdb'] = redis
    # Capture uploads after the DB dumps so completed uploads referenced by them exist.
    for folder in ['uploads', 'app-config']:
        for source in safe_files(ROOT / folder):
            paths[source.relative_to(ROOT).as_posix()] = source
    for optional in [ROOT / 'web-release.json']:
        if optional.exists():
            require(not optional.is_symlink(), 'Invalid release metadata')
            paths['config/' + optional.name] = optional
    if (ROOT / 'web-slots').exists():
        for source in safe_files(ROOT / 'web-slots'):
            paths['config/' + source.relative_to(ROOT).as_posix()] = source
    for name, source in paths.items():
        files[name] = {'bytes': source.stat().st_size, 'sha256': digest(source)}
    manifest = {'version': 1, 'snapshot': snapshot, 'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': files, 'databaseConsistency': 'individual pg_dump transactions; no cross-database atomic checkpoint', 'sourceHost': os.uname().nodename}
    manifest_file = stage / 'manifest.json'
    manifest_file.write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
    manifest_file.chmod(0o600)
    archive = stage / 'payload.tar.gz'
    with archive.open('wb') as raw, tarfile.open(fileobj=GuardedWriter(raw), mode='w:gz', compresslevel=1) as tar:
        for name, source in paths.items():
            tar.add(source, arcname=name, recursive=False)
        tar.add(manifest_file, arcname='manifest.json', recursive=False)
    archive.chmod(0o600)
    verify_tar(archive, manifest)
    partial = OUTBOX / (snapshot + '.tar.gz.age.partial')
    final = OUTBOX / (snapshot + '.tar.gz.age')
    export_bounded(['age', '--encrypt', '-r', config['ageRecipient'], str(archive)], partial)
    partial.chmod(0o640)
    shutil.chown(partial, group='item79-backup-reader')
    with partial.open('rb') as stream:
        os.fsync(stream.fileno())
    os.replace(partial, final)
    receipt = {'version': 1, 'snapshot': snapshot, 'filename': final.name, 'createdAt': manifest['createdAt'], 'bytes': final.stat().st_size, 'sha256': digest(final), 'fileCount': len(files), 'manifestSha256': digest(manifest_file)}
    latest = OUTBOX / 'latest.json.pending'
    latest.write_text(json.dumps(receipt), encoding='utf-8')
    latest.chmod(0o640)
    shutil.chown(latest, group='item79-backup-reader')
    os.replace(latest, OUTBOX / 'latest.json')
    return receipt


def main():
    import fcntl
    import signal
    def terminate(signum, _frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    os.umask(0o077)
    config = json.loads(CONFIG.read_text())
    with (ROOT / '.deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipt = build_snapshot(config)
    print(json.dumps({'event': 'encrypted_backup_ready', 'snapshot': receipt['snapshot'], 'bytes': receipt['bytes'], 'fileCount': receipt['fileCount']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        import traceback
        failure = ROOT / '.backup-last-error.log'
        failure.write_text(traceback.format_exc())
        failure.chmod(0o600)
        print(json.dumps({'event': 'backup_failed', 'errorType': type(error).__name__}))
        raise SystemExit(1)
