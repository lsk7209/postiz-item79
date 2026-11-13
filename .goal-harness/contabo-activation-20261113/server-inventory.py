import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time

root = Path('/opt/postiz-center-20261112')
dc = ['docker', 'compose', '--project-directory', str(root)]
def run(args):
    return subprocess.check_output(args)
def sql(query):
    return run(dc + ['exec', '-T', 'database', 'psql', '-U', 'postiz', '-d', 'postiz', '-At', '-c', query]).decode().strip()

containers = [json.loads(line) for line in run(['docker', 'ps', '--format', '{{json .}}']).decode().splitlines()]
counts = {table: int(sql('SELECT count(*) FROM "' + table + '"')) for table in ['User', 'Organization', 'Integration', 'Post', 'Media']}
# Hash secret-bearing rows inside this process. Never print row contents.
protected = {table: hashlib.sha256(sql('SELECT row_to_json(t)::text FROM (SELECT * FROM "' + table + '" ORDER BY id) t').encode()).hexdigest() for table in ['User', 'Organization', 'Integration', 'Post', 'Media']}
uploads = {str(p.relative_to(root/'uploads')): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'uploads').rglob('*')) if p.is_file()}
summary = {'counts': counts, 'protectedRowHashes': protected, 'uploads': uploads, 'configs': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['compose.yaml', 'app.env', '.env', 'wait-temporal.cjs']}, 'containers': [{'name': c['Names'], 'id': c['ID'], 'state': c['State']} for c in containers]}
if '--backup' in sys.argv:
    backup = root/'backups'/('activation-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    backup.mkdir(mode=0o700)
    for service, db, user in [('database', 'postiz', 'postiz'), ('temporal-db', 'temporal', 'temporal')]:
        file = backup/(db + '.dump')
        with file.open('wb') as out:
            subprocess.run(dc + ['exec', '-T', service, 'pg_dump', '-U', user, '-d', db, '-Fc'], stdout=out, check=True)
        file.chmod(0o600)
        assert file.stat().st_size > 1000
    with tarfile.open(backup/'private-files.tar.gz', 'w:gz') as tar:
        for name in ['compose.yaml', 'app.env', '.env', 'wait-temporal.cjs', 'uploads', 'app-config']:
            tar.add(root/name, arcname=name)
    (backup/'private-files.tar.gz').chmod(0o600)
    (backup/'inventory.json').write_text(json.dumps(summary, indent=2))
    (backup/'inventory.json').chmod(0o600)
    summary['backupPath'] = str(backup)
    summary['backupHashes'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in backup.iterdir() if p.is_file()}
print(json.dumps(summary))
