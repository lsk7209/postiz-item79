#!/usr/bin/env python3
"""Prepared restricted SSH entry point. Not installed or run by the current task.

Install root-owned and use an authorized_keys forced command with a dedicated key,
restrict, no PTY/forwarding; never grant this key an unrestricted shell or sudo.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path('/opt/postiz-center-20261112')
PREFIX = 'ghcr.io/lsk7209/postiz-item79@sha256:'

def image_argument(command):
    match = re.fullmatch(r'deploy (ghcr\.io/lsk7209/postiz-item79@sha256:[a-f0-9]{64})', command)
    if not match:
        raise ValueError('Only an exact Item79 image digest is accepted')
    return match[1]

def main():
    # Dry-run by default even if installed accidentally.
    if os.environ.get('ITEM79_ALLOW_DEPLOY') != 'true':
        raise SystemExit('Deployment is disabled; activation requires separate authorization')
    image = image_argument(os.environ.get('SSH_ORIGINAL_COMMAND', ''))
    import yaml
    assert ROOT.resolve() == ROOT and ROOT.is_dir()
    with (ROOT / '.deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        compose = ROOT / 'compose.yaml'
        before = compose.read_bytes()
        config = yaml.safe_load(before)
        assert config['name'] == 'postiz-center'
        app = config['services']['app']
        assert app['env_file'] == 'app.env'
        assert app['ports'] == ['127.0.0.1:34007:5000']
        args = ['docker', 'compose', '--project-directory', str(ROOT)]
        subprocess.run(['docker', 'pull', image], check=True)
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
            for _ in range(90):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:34007/auth/login', timeout=5) as response:
                        assert response.status == 200
                    with urllib.request.urlopen('http://127.0.0.1:34007/api/auth/can-register', timeout=5) as response:
                        assert json.load(response) == {'register': False}
                    print('Release verified; source/DB/uploads/other services preserved')
                    return
                except Exception:
                    time.sleep(5)
            raise RuntimeError('App readiness deadline exceeded')
        except BaseException:
            pending.write_bytes(before)
            os.replace(pending, compose)
            subprocess.run(args + ['up', '-d', '--no-deps', 'app'], check=True)
            raise

if __name__ == '__main__':
    main()
