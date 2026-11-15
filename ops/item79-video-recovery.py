#!/usr/bin/python3
"""Forced-command verifier: read/hash one owned backup member, no general shell."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys


def validate(q):
    if not isinstance(q, dict) or not re.fullmatch(r'/uploads/\d{4}/\d{1,2}/\d{1,2}/[a-f0-9]+\.(mp4|mov|m4v|webm)', q.get('path', ''), re.I):
        raise ValueError('Invalid owned video path')
    if not re.fullmatch('[a-f0-9]{64}', q.get('sha256', '')) or type(q.get('bytes')) is not int or not 0 < q['bytes'] <= 512 * 1024 ** 2:
        raise ValueError('Invalid content identity')
    if q.get('recovery'):
        r = q['recovery']
        if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}', r.get('sourceSnapshot', '')) or not re.fullmatch('[a-f0-9]{8,64}', r.get('snapshot', '')):
            raise ValueError('Invalid recovery identity')
    return q


def main():
    if len(sys.argv) != 1:
        raise ValueError('Arguments forbidden')
    raw = sys.stdin.buffer.read(16385)
    if len(raw) > 16384:
        raise ValueError('Request too large')
    q = validate(json.loads(raw))
    pins = json.loads(Path('/etc/item79-ops/video-recovery-pins.json').read_text())
    for name in ['item79-video-recovery.py', 'item79-video-cleanup.py']:
        if hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != pins[name]:
            raise ValueError('Unreviewed recovery helper')
    for path in ['/usr/local/lib/item79/item79-offsite.py', '/etc/item79-ops/offsite.json', '/var/lib/item79-offsite/repository/config']:
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != pins['runtimeFiles'][path]:
            raise ValueError('Offsite code, configuration or repository identity changed')
    spec = importlib.util.spec_from_file_location('cleanup_common', Path(__file__).with_name('item79-video-cleanup.py'))
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    # Fixed reviewed source only. Request bytes are data encoded into the fixed verifier.
    encoded = base64.b64encode(json.dumps(q).encode()).decode()
    exec(compile(common.VERIFY.replace('INPUT', encoded), '<fixed-recovery-verifier>', 'exec'), {})


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'state': 'VERIFICATION_FAILED', 'errorType': type(error).__name__}))
        sys.exit(1)
