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

    def release_case(self, fail_readiness=False, schema_changed=False, preview_failed=False, oauth_drift=False):
        old_image = 'ghcr.io/gitroomhq/postiz-app@sha256:' + 'b' * 64
        new_image = deploy.PREFIX + 'a' * 64
        revision = 'c' * 40
        policy = deploy.support_module('item79_release_policy')
        packet = {'revision': revision, 'sourcePolicy': policy.VERSION, 'dockerfileSha256': policy.DOCKERFILE_SHA256, 'changedPaths': ['ops/test.py']}
        web = types.SimpleNamespace(release=Mock(side_effect=RuntimeError('web release failed') if fail_readiness or preview_failed else None))
        config = {'name': 'postiz-center', 'services': {'app': {
            'image': old_image, 'env_file': 'app.env', 'ports': ['127.0.0.1:34007:5000'],
            'command': ['sh', '-c', 'node /app/wait-temporal.cjs && cp /config/oauth-nginx.conf /etc/nginx/nginx.conf && nginx && pnpm run pm2'],
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
            (root/'app-config').mkdir()
            (root/'app-config'/'oauth-nginx.conf').write_bytes(b'drifted' if oauth_drift else b'schema')
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
            with patch.object(deploy, 'ROOT', root), patch.object(deploy.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=100 * 1024**3)), patch.dict(deploy.os.environ, {'ITEM79_ALLOW_DEPLOY': 'true', 'SSH_ORIGINAL_COMMAND': 'deploy ' + new_image}, clear=True), patch.dict('sys.modules', {'fcntl': fake_lock, 'yaml': fake_yaml}), patch.object(deploy.sys, 'stdin', io.StringIO(json.dumps(packet))), patch.object(deploy.subprocess, 'check_output', side_effect=output), patch.object(deploy.subprocess, 'run') as run, patch.object(deploy, 'support_module', side_effect=lambda name: policy if name == 'item79_release_policy' else web):
                if schema_changed or fail_readiness or preview_failed or oauth_drift:
                    with self.assertRaises(RuntimeError):
                        deploy.main()
                    self.assertEqual((root/'compose.yaml').read_bytes(), before)
                else:
                    deploy.main()
                self.assertEqual((root/'compose.yaml').read_bytes(), before)
                self.assertFalse(any('up' in call.args[0] for call in run.call_args_list))
                if schema_changed or oauth_drift:
                    web.release.assert_not_called()
                else:
                    web.release.assert_called_once()
                    self.assertEqual(web.release.call_args.args[:2], (new_image, revision))

    def test_web_release_keeps_worker_compose_unchanged(self):
        self.release_case()

    def test_web_failure_cannot_recreate_worker(self):
        self.release_case(fail_readiness=True)

    def test_schema_change_cannot_replace_app(self):
        self.release_case(schema_changed=True)

    def test_failed_preview_leaves_production_app_untouched(self):
        self.release_case(preview_failed=True)

    def test_oauth_nginx_drift_blocks_web_release(self):
        self.release_case(oauth_drift=True)

    def test_backup_rejects_low_disk_before_running_dump(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'uploads').mkdir(); (root/'app-config').mkdir()
            with patch.object(deploy, 'ROOT', root), patch.object(deploy.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=0)), patch.object(deploy.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'Insufficient free space'):
                    deploy.backup_release([])
                run.assert_not_called()

    def test_backup_archive_contains_original_upload_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['uploads', 'app-config', 'backups']:
                (root/name).mkdir()
            original = b'original private upload bytes'
            (root/'uploads'/'video.mp4').write_bytes(original)
            for name in ['compose.yaml', 'app.env', '.env', 'wait-temporal.cjs']:
                (root/name).write_text('protected')
            def dump(command, stdout, **kwargs):
                stdout.write(b'PGDMP' + b'x' * 1100)
            with patch.object(deploy, 'ROOT', root), patch.object(deploy.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=100 * 1024**3)), patch.object(deploy.subprocess, 'run', side_effect=dump):
                backup = deploy.backup_release([])
                with deploy.tarfile.open(backup/'runtime-files.tar') as archive:
                    self.assertEqual(archive.extractfile('uploads/video.mp4').read(), original)

if __name__ == '__main__':
    unittest.main()
