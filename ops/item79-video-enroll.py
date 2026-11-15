#!/usr/bin/env python3
"""Enroll final upload copies from bounded existing receipts; never scan media trees."""
import hashlib
import json
from pathlib import Path
import re

BASE = Path('D:/youtube-money')
OUT = BASE / 'motion-engine/workspace/out'
DEST = Path('E:/codex-build/postiz-item79/video-cleanup/local-map.json')


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def objects(value):
    if isinstance(value, list):
        for item in value:
            yield from objects(item)
    elif isinstance(value, dict):
        yield value
        for item in value.values():
            if isinstance(item, (dict, list)):
                yield from objects(item)


def main():
    local = {}
    for name in ['object-next-ten-v2', 'object-next-twenty', 'object-next-seven-release-v2', 'object-three']:
        manifest = OUT / name / 'manifest.json'
        for item in objects(load(manifest)):
            sha = item.get('sha256') or item.get('videoSha256')
            value = item.get('path') or item.get('relativeVideo') or item.get('video')
            if re.fullmatch('[a-f0-9]{64}', str(sha)) and isinstance(value, str):
                path = Path(value)
                if not path.is_absolute():
                    path = manifest.parent / path
                if path.suffix.lower() == '.mp4' and path.exists():
                    local[sha] = path.resolve()
    qa = OUT / 'object-next-twenty-recheck-v2/clock-hands-overlap/qa.json'
    for item in objects(load(qa)):
        if item.get('sha256') and item.get('path'):
            local[item['sha256']] = Path(item['path']).resolve()
    ledger = load(BASE / 'upload-ledger.json')
    result = []
    for item in ledger.get('videos', []) + ledger.get('postizScheduledPosts', []):
        sha = item.get('sourceVideoSha256')
        path = local.get(sha)
        if not path and item.get('sourceArtifact'):
            path = (BASE / item['sourceArtifact']).resolve()
        if path and path.exists():
            result.append({'workflow': 'numberflipworld', 'sha256': sha, 'resolvedPath': str(path), 'postId': item.get('postizPostId'), 'videoId': item.get('id') or item.get('youtubeVideoId')})
    for item in load(OUT / 'object-three/manifest.json'):
        if item.get('youtubeVideoId') and item.get('sha256'):
            result.append({'workflow': 'numberflipworld', 'sha256': item['sha256'], 'resolvedPath': str(Path(item['path']).resolve()), 'postId': None, 'videoId': item['youtubeVideoId']})
    dog = BASE / 'shorts_factory'
    completion = load(dog / 'reports/hooked18_20261112/completion.json')
    dog_ledger = load(dog / 'reports/upload_improved18_20261113/ledger.json')
    if isinstance(dog_ledger, dict):
        dog_ledger = dog_ledger.get('items', dog_ledger.get('videos', []))
    by_hash = {item['sha256']: item for item in dog_ledger if item.get('sha256')}
    for item in completion['items']:
        entry = by_hash.get(item['sha256'], {})
        path = Path(item['output']).resolve()
        result.append({'workflow': 'shortsdog', 'sha256': item['sha256'], 'resolvedPath': str(path), 'postId': entry.get('postiz_post_id') or item.get('postizReservation', {}).get('postId'), 'videoId': entry.get('video_id') or item.get('youtube', {}).get('video_id')})
    for item in result:
        path = Path(item['resolvedPath'])
        if not path.is_file():
            raise RuntimeError('Enrolled local SHA mismatch')
        with path.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != item['sha256']:
                raise RuntimeError('Enrolled local SHA mismatch')
        item['localAssetId'] = hashlib.sha256((str(path) + ':' + item['sha256']).encode()).hexdigest()
        item['deleteEligible'] = bool(item['postId'])
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'enrolledCopies': len(result), 'postizMapped': sum(bool(item['postId']) for item in result), 'nativeOnlyProtected': sum(not item['postId'] for item in result)}))


if __name__ == '__main__':
    main()
