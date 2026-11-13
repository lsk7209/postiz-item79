import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
import base64
from unittest.mock import patch, Mock


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'ops' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


web = load('item79_web_release')
policy = load('item79_release_policy')


def route(target='http://postiz-center-app:5000'):
    return {'http': {'routers': {
        'postiz-item79-https': {'rule': 'Host(`postiz.item79.com`)', 'service': 'postiz-item79'},
        'postiz-item79-http': {'rule': 'Host(`postiz.item79.com`) && !PathPrefix(`/.well-known/acme-challenge/`)', 'service': 'postiz-item79'},
    }, 'services': {'postiz-item79': {'loadBalancer': {'servers': [{'url': target}]}}}}}


class WebReleaseTest(unittest.TestCase):
    def test_policy_rejects_retained_worker_and_dependency_changes(self):
        for path in ['apps/orchestrator/src/main.ts', 'libraries/nestjs-libraries/src/temporal/temporal.module.ts', 'package.json', 'pnpm-lock.yaml', 'Dockerfile.item79', 'apps/backend/src/api/routes/posts.controller.ts', '../ops/escape.py']:
            with self.assertRaises(RuntimeError):
                policy.validate({'sourcePolicy': policy.VERSION, 'dockerfileSha256': policy.DOCKERFILE_SHA256, 'changedPaths': [path]})
        policy.validate({'sourcePolicy': policy.VERSION, 'dockerfileSha256': policy.DOCKERFILE_SHA256, 'changedPaths': ['ops/item79_web_release.py', 'PROJECT_STATE.md']})

    def test_route_guard_rejects_unrelated_service(self):
        valid = route()
        web.validate_route(json.dumps(valid).encode(), None)
        valid['http']['routers']['postiz-item79-https']['rule'] = 'Host(`other.example`)'
        with self.assertRaises(RuntimeError):
            web.validate_route(json.dumps(valid).encode(), None)

    def test_web_slot_has_no_worker_or_schema_push(self):
        config = web.slot_config('image', 'blue', Path('/private/nginx.conf'))
        self.assertEqual(set(config['services']), {'web'})
        command = config['services']['web']['command'][-1]
        self.assertNotIn('pnpm run pm2', command)
        self.assertNotIn('prisma', command)
        self.assertNotIn('orchestrator', command)
        self.assertEqual(config['services']['web']['environment']['RUN_CRON'], '')
        self.assertTrue(config['services']['web']['ports'][0].startswith('127.0.0.1:'))

    def lifecycle(self, fail_warmup=False, fail_switch=False, fail_drain=False, keep_failed_candidate=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            route_file = root / 'route.json'
            original = json.dumps(route()).encode(); route_file.write_bytes(original)
            state = root / 'web-release.json'
            backup = root / 'backup'; backup.mkdir()
            identity = {'container': 'retained-worker', 'image': 'old', 'pid': 42, 'restarts': 0, 'pollerFingerprint': 'unchanged'}
            fake_yaml = types.SimpleNamespace(safe_dump=lambda value, **kwargs: json.dumps(value))
            def output(command):
                if command[-2:] == ['cat', '/etc/nginx/nginx.conf']:
                    return b'events {}\nhttp { server { listen 5000; } }'
                if command[-2:] == ['pm2', 'jlist']:
                    return b'[{"name":"frontend"},{"name":"backend"}]'
                if command[-3:] == ['ps', '-q', 'web']:
                    return b'web-id' if fail_drain else b''
                if fail_drain and command[:3] == ['docker', 'exec', 'web-id']:
                    return b'2'
                raise AssertionError(command)
            def health_wait(base, revision=None, attempts=120):
                if fail_warmup and base.startswith('http://127.'):
                    raise RuntimeError('candidate not ready')
                if fail_switch and base == web.DOMAIN and revision == 'new-revision':
                    raise RuntimeError('proxy switch failed')
            with patch.object(web, 'ROOT', root), patch.object(web, 'STATE', state), patch.object(web, 'ROUTE', route_file), patch.object(web, 'worker_identity', return_value=identity), patch.object(web, 'verify_runtime_closure', return_value='same-closure'), patch.object(web, 'live_schema_unchanged'), patch.object(web, 'wait_health', side_effect=health_wait), patch.object(web, 'health'), patch.object(web.time, 'sleep'), patch.object(web.Path, 'read_text', autospec=True, side_effect=lambda path, *a, **k: 'MemAvailable: 10000000 kB' if path.as_posix() == '/proc/meminfo' else Path.read_bytes(path).decode()), patch.dict('sys.modules', {'yaml': fake_yaml}), patch.object(web.subprocess, 'check_output', side_effect=output), patch.object(web.subprocess, 'run') as run:
                if fail_warmup or fail_switch or fail_drain:
                    with self.assertRaises(RuntimeError):
                        web.release('new-image', 'new-revision', ['docker', 'compose', 'original'], Mock(), lambda: backup)
                    self.assertEqual(route_file.read_bytes(), original)
                    self.assertFalse(state.exists())
                else:
                    web.release('new-image', 'new-revision', ['docker', 'compose', 'original'], Mock(), lambda: backup)
                    self.assertEqual(json.loads(state.read_text())['activeSlot'], 'blue')
                    self.assertEqual(json.loads(route_file.read_text())['http']['services']['postiz-item79']['loadBalancer']['servers'][0]['url'], 'http://postiz-item79-web-blue:5000')
                for call in run.call_args_list:
                    self.assertNotIn('app', call.args[0])
                    if fail_drain:
                        self.assertNotIn('stop', call.args[0])
                        self.assertNotIn('up', call.args[0])
                    if keep_failed_candidate:
                        self.assertNotIn('stop', call.args[0])
                self.assertFalse((root / 'web-release.pending.json').exists())

    def test_warmup_failure_keeps_public_route_and_worker(self):
        self.lifecycle(fail_warmup=True)

    def test_switch_failure_restores_previous_route(self):
        self.lifecycle(fail_switch=True)

    def test_success_changes_only_web_target(self):
        self.lifecycle()

    def test_interrupted_proxy_switch_restores_previous_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            original = json.dumps(route()).encode()
            route_file = root / 'route.json'; route_file.write_text(json.dumps(route('http://postiz-item79-web-blue:5000')))
            journal = root / 'web-release.pending.json'
            journal.write_text(json.dumps({'oldState': None, 'slot': 'blue', 'revision': 'new', 'workerImage': 'old', 'routeBefore': base64.b64encode(original).decode()}))
            with patch.object(web, 'ROOT', root), patch.object(web, 'STATE', root / 'web-release.json'), patch.object(web, 'ROUTE', route_file), patch.object(web, 'worker_identity', return_value={'image': 'old'}), patch.object(web, 'wait_health'):
                web.recover_pending([])
            self.assertEqual(route_file.read_bytes(), original)
            self.assertFalse(journal.exists())

    def test_busy_inactive_slot_is_not_stopped(self):
        with patch.object(web.subprocess, 'check_output', side_effect=[b'web-id'] + [b'2'] * 30), patch.object(web.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'active uploads'):
                web.wait_inactive_connections(['docker', 'compose'])

    def test_release_drain_failure_leaves_existing_inactive_slot_running(self):
        self.lifecycle(fail_drain=True)

    def test_rollback_retains_candidate_if_public_connections_have_not_drained(self):
        with patch.object(web, 'wait_inactive_connections', side_effect=[None, RuntimeError('upload still active')]):
            self.lifecycle(fail_switch=True, keep_failed_candidate=True)
