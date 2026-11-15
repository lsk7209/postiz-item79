"""Fail closed when an ordinary web release touches the retained worker contract."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

BASELINE = '2c951cf3b67520ad449bb7d5a9d850518dbf3a89'
VERSION = 'item79-web-v2-channel-analytics'
DOCKERFILE_SHA256 = 'd5bc042db036a92c2ea2950bc77d59c70b4de3a77b6df105b32071b9dcc4bddc'
FRONTEND = {
    'apps/frontend/src/components/launches/launches.component.tsx',
    'apps/frontend/src/components/launches/channel-account-label.tsx',
    'apps/frontend/src/components/launches/settings.modal.tsx',
    'apps/frontend/src/components/platform-analytics/render.analytics.tsx',
    'apps/frontend/src/components/platform-analytics/platform.analytics.tsx',
    'apps/backend/src/api/routes/channel-analytics.ts',
    'apps/backend/src/api/routes/analytics.controller.ts',
    'apps/backend/src/public-api/routes/v1/public.integrations.controller.ts',
    'Dockerfile.item79',
}


def allowed(path):
    part = PurePosixPath(path)
    if part.is_absolute() or '..' in part.parts or '\\' in path:
        return False
    return (path in FRONTEND or path.startswith(('ops/', 'tests/', '.goal-harness/', '.github/workflows/'))
            or path in {'.dockerignore', '.gitignore', 'PROJECT_STATE.md', 'ITEM79.md'}
            or ('/' not in path and path.endswith('.md')))


def validate(packet):
    if packet.get('sourcePolicy') != VERSION or packet.get('dockerfileSha256') != DOCKERFILE_SHA256:
        raise RuntimeError('Release policy or base image definition changed; deliberate review required')
    paths = packet.get('changedPaths')
    if not isinstance(paths, list) or not all(isinstance(path, str) and allowed(path) for path in paths):
        raise RuntimeError('Worker, schema, dependency or unsupported source change requires deliberate review')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--head', required=True)
    args = parser.parse_args()
    paths = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, args.head]).decode().splitlines()
    packet = {'sourcePolicy': VERSION, 'changedPaths': paths, 'dockerfileSha256': hashlib.sha256(Path('Dockerfile.item79').read_bytes()).hexdigest()}
    validate(packet)
    print(json.dumps(packet))


if __name__ == '__main__':
    main()
