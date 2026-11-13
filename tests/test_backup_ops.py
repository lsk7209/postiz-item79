import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import types


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'ops' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


backup = module('item79-backup')
export = module('item79-backup-export')
offsite = module('item79-offsite')


class BackupSafetyTest(unittest.TestCase):
    def test_export_rejects_shell_and_traversal(self):
        for value in ['../../etc/passwd', '20261113T050000Z-deadbeef;id', '', '20261113T050000Z-deadbeef\n']:
            with self.assertRaises(ValueError):
                export.snapshot_path(value)
        for value in ['whoami', 'fetch ../../etc/passwd', 'status; id', 'fetch 20261113T050000Z-deadbeef && id']:
            with patch.dict(export.os.environ, {'SSH_ORIGINAL_COMMAND': value}):
                with self.assertRaises(ValueError):
                    export.main()

    def test_snapshot_hash_check_detects_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'snapshot.tar.gz'
            content = b'private recovery bytes'
            with tarfile.open(archive, 'w:gz') as tar:
                for name, data in [('uploads/video.mp4', content), ('manifest.json', b'{}')]:
                    info = tarfile.TarInfo(name); info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
            manifest = {'files': {'uploads/video.mp4': {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}}}
            backup.verify_tar(archive, manifest)
            manifest['files']['uploads/video.mp4']['sha256'] = '0' * 64
            with self.assertRaisesRegex(RuntimeError, 'content mismatch'):
                backup.verify_tar(archive, manifest)

    def test_offsite_blocks_unsafe_archive_members(self):
        for name, link in [('../escape', False), ('/etc/escape', False), ('safe/link', True)]:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = root / 'bad.tar.gz'
                with tarfile.open(archive, 'w:gz') as tar:
                    info = tarfile.TarInfo(name)
                    if link:
                        info.type = tarfile.SYMTYPE; info.linkname = '/etc/passwd'
                    else:
                        info.size = 1
                    tar.addfile(info, None if link else io.BytesIO(b'x'))
                with self.assertRaisesRegex(RuntimeError, 'Unsafe snapshot'):
                    offsite.extract_verified(archive, root / 'restore', '0' * 64)
                self.assertFalse((root / 'escape').exists())

    def test_restore_requires_exact_manifest_and_file_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / 'original'; payload.mkdir()
            (payload / 'video').write_bytes(b'original')
            manifest = {'files': {'video': {'bytes': 8, 'sha256': hashlib.sha256(b'original').hexdigest()}}}
            (payload / 'manifest.json').write_text(json.dumps(manifest))
            offsite.validate_payload(payload, manifest)
            (payload / 'video').write_bytes(b'changed!')
            with self.assertRaisesRegex(RuntimeError, 'checksum'):
                offsite.validate_payload(payload, manifest)

    def test_backup_refuses_symlink_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, 'Invalid snapshot source'):
                backup.safe_files(root / 'missing')
            real = root / 'real'; real.mkdir()
            link = root / 'linked'
            try:
                link.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest('This platform does not grant test symlink creation')
            with self.assertRaisesRegex(RuntimeError, 'Invalid snapshot source'):
                backup.safe_files(link)

    def test_failed_snapshot_removes_only_generated_plaintext(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            outbox = root / 'outbox'; outbox.mkdir()
            original = root / 'original-backup'; original.write_bytes(b'keep')
            def failed(config, identifier, stage):
                (stage / 'app.env').write_text('private scratch')
                (outbox / (identifier + '.tar.gz.age.partial')).write_bytes(b'unfinished')
                raise RuntimeError('injected after secret capture')
            with patch.object(backup, 'ROOT', root), patch.object(backup, 'OUTBOX', outbox), patch.object(backup, '_build_snapshot', side_effect=failed):
                with self.assertRaisesRegex(RuntimeError, 'injected'):
                    backup.build_snapshot({})
            self.assertEqual(list((root / 'ops-staging').iterdir()), [])
            self.assertEqual(list(outbox.iterdir()), [])
            self.assertEqual(original.read_bytes(), b'keep')

    def test_termination_exception_also_cleans_plaintext_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            outbox = root / 'outbox'; outbox.mkdir()
            def terminated(config, identifier, stage):
                (stage / 'app.env').write_text('private scratch')
                raise SystemExit(143)
            with patch.object(backup, 'ROOT', root), patch.object(backup, 'OUTBOX', outbox), patch.object(backup, '_build_snapshot', side_effect=terminated):
                with self.assertRaises(SystemExit):
                    backup.build_snapshot({})
            self.assertEqual(list((root / 'ops-staging').iterdir()), [])

    def test_archive_writer_stops_at_disk_reserve(self):
        with patch.object(backup.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=backup.RESERVE)):
            output = io.BytesIO()
            with self.assertRaisesRegex(RuntimeError, 'reserve reached'):
                backup.GuardedWriter(output).write(b'private bytes')
            self.assertEqual(output.getvalue(), b'')

    def test_export_only_serves_encrypted_outbox(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(export, 'ROOT', root):
                actual = export.snapshot_path('20261113T050000Z-deadbeef')
                self.assertEqual(actual, root / '20261113T050000Z-deadbeef.tar.gz.age')
