import datetime
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('cleanup', Path(__file__).parents[1] / 'ops/item79-video-cleanup.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CleanupTests(unittest.TestCase):
    def test_enrollment_hash_drift_stops_before_network_or_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'local-map.json').write_text('[]')
            config = {'runnerSha256': c.digest(Path(c.__file__)), 'gateSha256': c.GATE_SHA256, 'localMapSha256': c.digest(root / 'local-map.json')}
            (root / 'installation.json').write_text(json.dumps(config))
            with patch.object(c, 'ROOT', root):
                c.verify_installation()
                (root / 'local-map.json').write_text('[{}]')
                with self.assertRaises(RuntimeError):
                    c.verify_installation()

    def test_public_window_resets_after_private_or_missing(self):
        self.assertEqual(c.update_observed({'a': 'old', 'b': 'old'}, ['a', 'c'], 'now'), {'a': 'old', 'c': 'now'})

    def test_other_reservation_protects_same_local_bytes(self):
        one = {'sha256': 'a', 'postId': 'p', 'resolvedPath': 'x', 'deleteEligible': True}
        self.assertEqual(c.local_candidates([one, one], {'sha256': 'a', 'postIds': ['p']}), [one])
        self.assertEqual(c.local_candidates([one, one | {'postId': None}], {'sha256': 'a', 'postIds': ['p']}), [])
        self.assertEqual(c.local_candidates([one, one | {'postId': 'future'}], {'sha256': 'a', 'postIds': ['p']}), [])

    def execute_case(self, apply, responses):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'local-map.json').write_text('[]')
            with patch.object(c, 'ROOT', root), patch.object(c, 'remote', side_effect=responses) as remote, patch.object(c, 'delete_local') as remove:
                result = c.execute(apply)
                return result, remote.call_count, remove.call_count

    def test_no_candidates_never_calls_recovery_or_removal(self):
        r, calls, removed = self.execute_case(True, [{'publicIds': [], 'capturedAt': c.utc(), 'protectedCounts': {'queue': 66}, 'candidates': []}])
        self.assertEqual((r['state'], calls, removed), ('COMPLETED', 1, 0))

    def test_backup_failure_stops_server_and_local_delete(self):
        candidate = {'path': '/uploads/x.mp4', 'sha256': 'a', 'bytes': 1}
        r, calls, removed = self.execute_case(True, [{'publicIds': [], 'capturedAt': c.utc(), 'protectedCounts': {}, 'candidates': [candidate]}, RuntimeError('unavailable')])
        self.assertEqual((r['state'], calls, removed), ('PARTIAL_REQUIRES_RECONCILIATION', 2, 0))

    def test_ambiguous_server_result_never_removes_pc_copy(self):
        candidate = {'path': '/uploads/x.mp4', 'sha256': 'a', 'bytes': 1}
        r, calls, removed = self.execute_case(True, [{'publicIds': [], 'capturedAt': c.utc(), 'protectedCounts': {}, 'candidates': [candidate]}, {'restoredAndHashed': True}, RuntimeError('SSH disconnected')])
        self.assertEqual((r['state'], calls, removed), ('PARTIAL_REQUIRES_RECONCILIATION', 3, 0))

    def test_restart_reconciles_server_ack_before_resuming_local(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'receipts').mkdir(); (root / 'local-map.json').write_text('[]')
            candidate = {'path': '/uploads/x.mp4', 'sha256': 'a', 'bytes': 1}
            intent = {'state': 'VERIFIED_INTENT', 'candidate': candidate, 'operationId': 'op', 'recovery': {'snapshot': 'r'}}
            journal = root / 'receipts/old.json'; journal.write_text(json.dumps(intent))
            responses = [
                {'publicIds': [], 'capturedAt': c.utc(), 'protectedCounts': {}, 'candidates': []},
                {'state': 'REMOVED', 'operationId': 'op', 'expected': candidate, 'recovery': intent['recovery']},
                {'restoredAndHashed': True}, {'permitted': True},
            ]
            with patch.object(c, 'ROOT', root), patch.object(c, 'remote', side_effect=responses) as remote:
                self.assertEqual(c.execute(True)['state'], 'COMPLETED')
                self.assertEqual(remote.call_count, 4)
            self.assertEqual(json.loads(journal.read_text())['state'], 'COMPLETED')

    def test_stale_replayed_receipt_never_allows_local_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'receipts').mkdir(); (root / 'local-map.json').write_text('[]')
            candidate = {'path': '/uploads/x.mp4', 'sha256': 'a', 'bytes': 1}
            intent = {'state': 'VERIFIED_INTENT', 'candidate': candidate, 'operationId': 'op', 'recovery': {'snapshot': 'r'}}
            (root / 'receipts/old.json').write_text(json.dumps(intent))
            responses = [{'publicIds': [], 'capturedAt': c.utc(), 'protectedCounts': {}, 'candidates': []}, {'state': 'REMOVED', 'operationId': 'different'}]
            with patch.object(c, 'ROOT', root), patch.object(c, 'remote', side_effect=responses) as remote, patch.object(c, 'delete_local') as remove:
                self.assertEqual(c.execute(True)['state'], 'PARTIAL_REQUIRES_RECONCILIATION')
                self.assertEqual(remote.call_count, 2); remove.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows exclusive handle')
    def test_windows_exclusive_delete_hash_and_open_file_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'test.mp4'; p.write_bytes(b'test')
            with self.assertRaises(RuntimeError):
                c.exclusive_remove(p, '0' * 64, 4)
            self.assertTrue(p.exists())
            with p.open('rb'):
                with self.assertRaises(OSError):
                    c.exclusive_remove(p, c.digest(p), 4)
            self.assertTrue(p.exists())
            c.exclusive_remove(p, c.digest(p), 4)
            self.assertFalse(p.exists())


if __name__ == '__main__':
    unittest.main()
