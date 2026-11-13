#!/usr/bin/env python3
"""Read-only SSH forced command; exports encrypted snapshots and safe receipts only."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path('/var/lib/item79-backup-export')
PATTERN = r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}'


def snapshot_path(identifier):
    if not re.fullmatch(PATTERN, identifier):
        raise ValueError('Invalid snapshot identifier')
    file = ROOT / (identifier + '.tar.gz.age')
    if file.is_symlink() or file.resolve().parent != ROOT:
        raise ValueError('Invalid export path')
    return file


def main():
    command = os.environ.get('SSH_ORIGINAL_COMMAND', '')
    if command == 'status':
        receipt = json.loads((ROOT / 'latest.json').read_text())
        file = snapshot_path(receipt['snapshot'])
        if file.stat().st_size != receipt['bytes']:
            raise RuntimeError('Incomplete encrypted snapshot')
        receipt['sourceFreeBytes'] = shutil.disk_usage(ROOT).free
        receipt['exportBytes'] = sum(p.stat().st_size for p in ROOT.glob('*.tar.gz.age'))
        print(json.dumps(receipt))
        return
    match = re.fullmatch('fetch (' + PATTERN + ')', command)
    if not match:
        raise ValueError('Only encrypted backup status/fetch is permitted')
    with snapshot_path(match[1]).open('rb') as source:
        shutil.copyfileobj(source, sys.stdout.buffer, length=1024 * 1024)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Encrypted backup export rejected', file=sys.stderr)
        raise SystemExit(1)
