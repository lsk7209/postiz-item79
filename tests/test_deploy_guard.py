import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch, Mock
import io
import json
import tempfile
import types

spec = importlib.util.spec_from_file_location('deploy', Path(__file__).parents[1] / 'ops/contabo-deploy.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)

class DeploymentGuardTest(unittest.TestCase):
    def test_accepts_only_our_immutable_image(self):
        image = 'ghcr.io/lsk7209/postiz-item79@sha256:' + 'a' * 64
        self.assertEqual(deploy.image_argument('deploy ' + image), image)
        for command in ['deploy ghcr.io/lsk7209/postiz-item79:latest',
                        'deploy ghcr.io/other/postiz@sha256:' + 'a' * 64,
                        'deploy ' + image + '; reboot', 'whoami', 'deploy ' + image + '\n']:
            with self.assertRaises(ValueError):
                deploy.image_argument(command)

    def test_default_cannot_mutate_server(self):
        with patch.dict(deploy.os.environ, {}, clear=True), patch.object(deploy.subprocess, 'run') as run:
            with self.assertRaisesRegex(SystemExit, 'Deployment is disabled'):
                deploy.main()
            run.assert_not_called()

    def release_case(self, fail_readiness=False, schema_changed=False, preview_failed=False):
        old_image = 'ghcr.io/gitroomhq/postiz-app@sha256:' + 'b' * 64
        new_image = deploy.PREFIX + 'a' * 64
        revision = 'c' * 40
        config = {'name': 'postiz-center', 'services': {'app': {
            'image': old_image, 'env_file': 'app.env', 'ports': ['127.0.0.1:34007:5000'],
            'command': ['sh', '-c', 'node /app/wait-temporal.cjs && nginx && pnpm run pm2'],
            'mem_limit': '4g', 'cpus': 2}}, 'networks': {'postiz-front': {'name': 'imcloud-postiz-front'}}}
        fake_yaml = types.SimpleNamespace(safe_load=json.loads, safe_dump=json.dumps)
        fake_lock = types.SimpleNamespace(flock=Mock(), LOCK_EX=1, LOCK_NB=2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root/'backups').mkdir()
            before = json.dumps(config).encode()
            (root/'compose.yaml').write_bytes(before)
            for name in ['app.env', '.env', 'wait-temporal.cjs']:
                (root/name).write_text('protected')
            def output(command):
                if command[:3] == ['docker', 'image', 'inspect']:
                    return json.dumps([{'Config': {'Labels': {'org.opencontainers.image.revision': revision}}}]).encode()
                if command[-3:] == ['ps', '-q', 'app']:
                    return b'old-container'
                if command[1] == 'exec':
                    return b'schema'
                if command[1] == 'run':
                    return b'changed' if schema_changed else b'schema'
                raise AssertionError(command)
            with patch.object(deploy, 'ROOT', root), patch.dict(deploy.os.environ, {'ITEM79_ALLOW_DEPLOY': 'true', 'SSH_ORIGINAL_COMMAND': 'deploy ' + new_image}, clear=True), patch.dict('sys.modules', {'fcntl': fake_lock, 'yaml': fake_yaml}), patch.object(deploy.sys, 'stdin', io.StringIO(json.dumps({'revision': revision}))), patch.object(deploy.subprocess, 'check_output', side_effect=output), patch.object(deploy.subprocess, 'run') as run, patch.object(deploy, 'validate_preview', side_effect=RuntimeError('preview failed') if preview_failed else None) as preview, patch.object(deploy, 'backup_release') as backup, patch.object(deploy, 'readiness', side_effect=[RuntimeError('failed'), None] if fail_readiness else None) as ready:
                if schema_changed or fail_readiness or preview_failed:
                    with self.assertRaises(RuntimeError):
                        deploy.main()
                    self.assertEqual((root/'compose.yaml').read_bytes(), before)
                else:
                    deploy.main()
                    self.assertEqual(json.loads((root/'compose.yaml').read_text())['services']['app']['image'], new_image)
                if schema_changed or preview_failed:
                    if schema_changed:
                        preview.assert_not_called()
                    backup.assert_not_called()
                    self.assertFalse(any('up' in call.args[0] for call in run.call_args_list))
                else:
                    backup.assert_called_once()
                    ready.assert_any_call(unittest.mock.ANY, new_image)
                    if fail_readiness:
                        ready.assert_any_call(unittest.mock.ANY, old_image, customized=False)

    def test_release_changes_only_image_after_backup(self):
        self.release_case()

    def test_failed_release_restores_exact_compose_and_checks_old_image(self):
        self.release_case(fail_readiness=True)

    def test_schema_change_cannot_replace_app(self):
        self.release_case(schema_changed=True)

    def test_failed_preview_leaves_production_app_untouched(self):
        self.release_case(preview_failed=True)

if __name__ == '__main__':
    unittest.main()
