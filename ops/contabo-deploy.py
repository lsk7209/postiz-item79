#!/usr/bin/env python3
"""Restricted SSH entry point for the dedicated Item79 app release.

Install root-owned and use an authorized_keys forced command with a dedicated key,
restrict, no PTY/forwarding; never grant this key an unrestricted shell or sudo.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import tempfile
import hashlib
import secrets
import tarfile
import urllib.request
import urllib.error

ROOT = Path('/opt/postiz-center-20261112')
PREFIX = 'ghcr.io/lsk7209/postiz-item79@sha256:'
SCHEMA = '/app/libraries/nestjs-libraries/src/database/prisma/schema.prisma'

def image_argument(command):
    match = re.fullmatch(r'deploy (ghcr\.io/lsk7209/postiz-item79@sha256:[a-f0-9]{64})', command)
    if not match:
        raise ValueError('Only an exact Item79 image digest is accepted')
    return match[1]

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def readiness(args, image, customized=True):
    for _ in range(90):
        try:
            with urllib.request.urlopen('http://127.0.0.1:34007/auth/login', timeout=5) as response:
                require(response.status == 200, 'Login is unavailable')
            with urllib.request.urlopen('http://127.0.0.1:34007/api/auth/can-register', timeout=5) as response:
                require(json.load(response) == {'register': False}, 'Registration must remain closed')
            container = subprocess.check_output(args + ['ps', '-q', 'app']).decode().strip()
            actual = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
            require(actual['Config']['Image'] == image, 'Running image does not match release')
            if customized:
                # An unknown route returns 404. The real protected route must return 401.
                request = urllib.request.Request('http://127.0.0.1:34007/api/integrations/deploy-smoke/google-account-label', data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
                try:
                    urllib.request.urlopen(request, timeout=5)
                    raise RuntimeError('Custom endpoint unexpectedly allowed anonymous access')
                except urllib.error.HTTPError as error:
                    require(error.code == 401, 'Custom backend route is unavailable')
            return
        except Exception:
            time.sleep(5)
    raise RuntimeError('App readiness deadline exceeded')

def backup_release(args):
    backup = ROOT / 'backups' / ('release-' + str(time.time_ns()))
    backup.mkdir(mode=0o700)
    for name in ['compose.yaml', 'app.env', '.env', 'wait-temporal.cjs']:
        shutil.copy2(ROOT / name, backup / name)
        (backup / name).chmod(0o600)
    with (backup / 'postiz.dump').open('wb') as output:
        subprocess.run(args + ['exec', '-T', 'database', 'pg_dump', '-U', 'postiz', '-d', 'postiz', '-Fc'], stdout=output, check=True)
    (backup / 'postiz.dump').chmod(0o600)
    require((backup / 'postiz.dump').stat().st_size > 1000, 'Database backup is empty')
    with tarfile.open(backup / 'runtime-files.tar', 'w') as archive:
        for name in ['uploads', 'app-config']:
            archive.add(ROOT / name, arcname=name)
    (backup / 'runtime-files.tar').chmod(0o600)
    return backup

def validate_preview(image, config, args):
    """Run only web processes against a private DB clone, never production workers."""
    import yaml
    parent = ROOT / 'preview'
    parent.mkdir(mode=0o700, exist_ok=True)
    require(parent.resolve().parent == ROOT, 'Unexpected preview directory')
    suffix = str(time.time_ns())
    preview = parent / suffix
    preview.mkdir(mode=0o700)
    project = 'postiz-item79-preview-' + suffix
    network = project + '_default'
    namespace = project
    password = secrets.token_hex(32)
    values = {
        'JWT_SECRET': secrets.token_hex(32), 'DATABASE_URL': 'postgresql://postiz:' + password + '@preview-db:5432/postiz',
        'REDIS_URL': 'redis://preview-redis:6379', 'TEMPORAL_ADDRESS': 'temporal:7233', 'TEMPORAL_NAMESPACE': namespace,
        'MAIN_URL': 'http://127.0.0.1:34008', 'FRONTEND_URL': 'http://127.0.0.1:34008',
        'NEXT_PUBLIC_BACKEND_URL': 'http://127.0.0.1:34008/api', 'BACKEND_INTERNAL_URL': 'http://localhost:3000',
        'STORAGE_PROVIDER': 'local', 'UPLOAD_DIRECTORY': '/uploads', 'NEXT_PUBLIC_UPLOAD_DIRECTORY': '/uploads',
        'IS_GENERAL': 'true', 'DISABLE_REGISTRATION': 'true', 'NX_ADD_PLUGINS': 'false', 'RUN_CRON': '', 'NOT_SECURED': 'true',
    }
    env = preview / 'web.env'
    env.write_text(''.join(k + '=' + v + '\n' for k, v in values.items()))
    env.chmod(0o600)
    settings = {'name': project, 'services': {
        'preview-db': {'image': config['services']['database']['image'], 'environment': {'POSTGRES_USER': 'postiz', 'POSTGRES_DB': 'postiz', 'POSTGRES_PASSWORD': password}, 'mem_limit': '512m', 'cpus': 0.5, 'healthcheck': {'test': ['CMD-SHELL', 'pg_isready -U postiz -d postiz'], 'interval': '2s', 'timeout': '2s', 'retries': 45}},
        'preview-redis': {'image': config['services']['redis']['image'], 'mem_limit': '128m', 'cpus': 0.25},
        'web': {'image': image, 'env_file': 'web.env', 'ports': ['127.0.0.1:34008:5000'], 'volumes': [str(ROOT / 'uploads') + ':/uploads:ro'], 'mem_limit': '4g', 'cpus': 2,
                'command': ['sh', '-c', 'nginx && pnpm --filter ./apps/frontend run pm2 && pnpm --filter ./apps/backend run pm2 && pm2 logs']},
    }, 'networks': {'default': {'internal': True}}}
    compose = preview / 'compose.yaml'
    compose.write_text(yaml.safe_dump(settings, sort_keys=False))
    compose.chmod(0o600)
    pc = ['docker', 'compose', '--project-directory', str(preview)]
    temporal = subprocess.check_output(args + ['ps', '-q', 'temporal']).decode().strip()
    connected = False
    try:
        subprocess.run(['docker', 'exec', temporal, 'tctl', '--address', 'temporal:7233', '--namespace', namespace, 'namespace', 'register', '--retention', '1'], stdout=subprocess.DEVNULL, check=True)
        subprocess.run(pc + ['up', '-d', '--wait', 'preview-db', 'preview-redis'], check=True)
        subprocess.run(['docker', 'network', 'connect', '--alias', 'temporal', network, temporal], check=True)
        connected = True
        dump = preview / 'postiz.dump'
        with dump.open('wb') as out:
            subprocess.run(args + ['exec', '-T', 'database', 'pg_dump', '-U', 'postiz', '-d', 'postiz', '-Fc'], stdout=out, check=True)
        dump.chmod(0o600)
        with dump.open('rb') as inp:
            subprocess.run(pc + ['exec', '-T', 'preview-db', 'pg_restore', '-U', 'postiz', '-d', 'postiz', '--exit-on-error', '--no-owner', '--no-acl'], stdin=inp, stdout=subprocess.DEVNULL, check=True)
        subprocess.run(pc + ['up', '-d', '--no-deps', 'web'], check=True)
        for _ in range(90):
            try:
                with urllib.request.urlopen('http://127.0.0.1:34008/auth/login', timeout=5) as response:
                    require(response.status == 200, 'Preview login unavailable')
                with urllib.request.urlopen('http://127.0.0.1:34008/api/auth/can-register', timeout=5) as response:
                    require(json.load(response) == {'register': False}, 'Preview backend unavailable')
                request = urllib.request.Request('http://127.0.0.1:34008/api/integrations/deploy-smoke/google-account-label', data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
                try:
                    urllib.request.urlopen(request, timeout=5)
                    raise RuntimeError('Preview endpoint allows anonymous edits')
                except urllib.error.HTTPError as error:
                    require(error.code == 401, 'Preview custom route unavailable')
                print('Private preview passed: cloned DB, read-only uploads, isolated Temporal namespace, web-only, no outbound network or publishing workers')
                return
            except Exception:
                time.sleep(5)
        raise RuntimeError('Private preview failed; production app was not replaced')
    finally:
        cleanup_errors = []
        commands = [pc + ['stop']]
        # Attempt disconnect even if connect's result was interrupted or uncertain.
        commands.append(['docker', 'network', 'disconnect', network, temporal])
        # Remove only the disposable containers/network; keep dumps, configs and production volumes.
        commands.append(pc + ['down'])
        for command in commands:
            try:
                result = subprocess.run(command, check=False)
            except Exception:
                cleanup_errors.append(command[1:])
                continue
            if result.returncode and (connected or command[1] != 'network'):
                cleanup_errors.append(command[1:])
        attached = json.loads(subprocess.check_output(['docker', 'inspect', temporal, '--format', '{{json .NetworkSettings.Networks}}']))
        remaining = subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project]).strip()
        require(network not in attached and not remaining, 'Preview resources remain attached')
        require(not cleanup_errors, 'Preview cleanup incomplete; production app was not replaced')

def main():
    # Dry-run by default even if installed accidentally.
    if os.environ.get('ITEM79_ALLOW_DEPLOY') != 'true':
        raise SystemExit('Deployment is disabled; activation requires separate authorization')
    import fcntl
    image = image_argument(os.environ.get('SSH_ORIGINAL_COMMAND', ''))
    import yaml
    require(ROOT.resolve() == ROOT and ROOT.is_dir(), 'Unexpected deployment root')
    # The deploy job grants only packages:read; its short-lived token is never stored.
    packet = json.loads(sys.stdin.read(16384))
    revision = packet.get('revision', '')
    require(re.fullmatch('[a-f0-9]{40}', revision) is not None, 'Exact source revision required')
    with (ROOT / '.deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        compose = ROOT / 'compose.yaml'
        before = compose.read_bytes()
        config = yaml.safe_load(before)
        require(config['name'] == 'postiz-center', 'Unexpected compose project')
        app = config['services']['app']
        require(app['env_file'] == 'app.env', 'Unexpected app environment file')
        require(app['ports'] == ['127.0.0.1:34007:5000'], 'App must remain loopback-only')
        require(app['command'] == ['sh', '-c', 'node /app/wait-temporal.cjs && nginx && pnpm run pm2'], 'Startup dependency guard changed')
        require(app['mem_limit'] == '4g' and app['cpus'] == 2, 'Resource limits changed')
        require(config['networks']['postiz-front']['name'] == 'imcloud-postiz-front', 'Unexpected front network')
        args = ['docker', 'compose', '--project-directory', str(ROOT)]
        with tempfile.TemporaryDirectory(prefix='item79-registry-') as registry:
            if packet.get('registryToken'):
                subprocess.run(['docker', '--config', registry, 'login', 'ghcr.io', '-u', packet['registryUser'], '--password-stdin'], input=packet['registryToken'].encode(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(['docker', '--config', registry, 'pull', image], check=True)
        metadata = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
        require(metadata['Config']['Labels'].get('org.opencontainers.image.revision') == revision, 'Image/source revision mismatch')
        old_container = subprocess.check_output(args + ['ps', '-q', 'app']).decode().strip()
        old_schema = subprocess.check_output(['docker', 'exec', old_container, 'cat', SCHEMA])
        new_schema = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'cat', image, SCHEMA])
        require(old_schema == new_schema, 'Schema changes require separate migration review')
        validate_preview(image, config, args)
        config_hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ['app.env', '.env', 'wait-temporal.cjs']}
        backup_release(args)
        # Existing digest/compose preserved. Only the app image changes.
        backup = ROOT / 'backups' / ('compose.pre-release-' + str(time.time_ns()) + '.yaml')
        backup.write_bytes(before)
        os.chmod(backup, 0o600)
        app['image'] = image
        pending = compose.with_suffix('.pending')
        pending.write_text(yaml.safe_dump(config, sort_keys=False))
        os.chmod(pending, 0o600)
        os.replace(pending, compose)
        try:
            subprocess.run(args + ['config', '--quiet'], check=True)
            subprocess.run(args + ['up', '-d', '--no-deps', 'app'], check=True)
            readiness(args, image)
            require(all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in config_hashes.items()), 'Protected app configuration changed')
            print(json.dumps({'releasedImage': image, 'revision': revision, 'schemaUnchanged': True, 'protectedConfigUnchanged': True}))
        except BaseException:
            pending.write_bytes(before)
            os.replace(pending, compose)
            subprocess.run(args + ['up', '-d', '--no-deps', 'app'], check=True)
            readiness(args, yaml.safe_load(before)['services']['app']['image'], customized=False)
            print('Previous app image restored and readiness verified', file=sys.stderr)
            raise

if __name__ == '__main__':
    main()
