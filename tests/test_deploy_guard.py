import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

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

if __name__ == '__main__':
    unittest.main()
