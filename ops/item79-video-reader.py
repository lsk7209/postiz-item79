#!/usr/bin/python3
"""Forced-command PC reader. No arbitrary Python, Docker or remove mode."""
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import sys


def validate(q):
    if not isinstance(q, dict) or q.get('mode') not in ['export', 'receipt', 'local-check']:
        raise ValueError('Read-only modes only')
    if q['mode'] != 'export' and not re.fullmatch('[a-f0-9]{32}', q.get('operationId', '')):
        raise ValueError('Invalid operation ID')
    return q


def request(q, server):
    q = validate(q)
    if q['mode'] == 'export':
        return server.run(exporting=True)
    exported = server.run(exporting=True)
    intent = next((r for r in exported['receipts'] if r['operationId'] == q['operationId']), None)
    if not intent or intent.get('gateSha256') != server.common.GATE_SHA256:
        raise ValueError('No completed enrolled operation')
    ack = server.gate({'mode': 'receipt', 'operationId': q['operationId']})
    if not server.ack_matches(ack, intent):
        raise ValueError('Unacknowledged operation')
    if q['mode'] == 'receipt':
        return ack
    # Observation and candidate are taken from the authoritative server, never from PC input.
    return server.gate({'mode': 'local-check', 'observed': exported['observed'], 'expected': intent['candidate']})


def main():
    if len(sys.argv) != 1:
        raise ValueError('Arguments forbidden')
    raw = sys.stdin.buffer.read(16385)
    if len(raw) > 16384:
        raise ValueError('Request too large')
    q = validate(json.loads(raw))
    pins = json.loads(Path('/etc/item79-ops/video-reader-pins.json').read_text())
    for name in ['item79-video-reader.py', 'item79-video-cleanup.py', 'item79-server-video-cleanup.py']:
        if hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != pins[name]:
            raise ValueError('Unreviewed receipt reader')
    spec = importlib.util.spec_from_file_location('server_cleanup', Path(__file__).with_name('item79-server-video-cleanup.py'))
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    print(json.dumps(request(q, server)))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'state': 'READ_FAILED_CLOSED', 'errorType': type(error).__name__}))
        sys.exit(1)
