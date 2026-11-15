import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'ops' / file)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


s = module('server_cleanup_test', 'item79-server-video-cleanup.py')
c = s.common
r = module('recovery_test', 'item79-video-recovery.py')
reader = module('reader_test', 'item79-video-reader.py')


class ServerCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = {'path': '/uploads/2026/11/13/abcd.mp4', 'sha256': 'a' * 64, 'bytes': 4, 'postIds': ['p'], 'mediaIds': ['m']}
        self.current = {'capturedAt': c.utc(), 'publicIds': ['public'], 'protectedCounts': {}, 'candidates': [self.candidate]}
        self.proof = {'restoredAndHashed': True, 'sha256': 'a' * 64, 'bytes': 4, 'snapshot': 'b' * 64}

    def test_server_has_no_pc_dependency_and_pins_proof_before_removal(self):
        def gate(q):
            if q['mode'] == 'inspect': return self.current
            self.assertEqual(q['mode'], 'remove')
            journals = list((self.root / 'receipts').glob('*.json')); self.assertEqual(len(journals), 1)
            intent = json.loads(journals[0].read_text()); self.assertEqual(intent['state'], 'VERIFIED_INTENT')
            self.assertEqual(intent['recovery'], self.proof)
            return {'removed': self.candidate['path'], 'operationId': q['operationId'], **self.candidate, 'recovery': self.proof}
        with patch.object(s, 'ROOT', self.root), patch.object(s, 'gate', side_effect=gate), patch.object(s, 'verify', return_value=self.proof):
            result = s.execute(True)
        self.assertEqual((result['state'], len(result['serverRemoved'])), ('COMPLETED', 1))
        intent = json.loads(next((self.root / 'receipts').glob('*.json')).read_text())
        self.assertEqual(intent['state'], 'COMPLETED'); self.assertEqual(intent['gateSha256'], c.GATE_SHA256)

    def test_failed_offsite_proof_prevents_any_remove(self):
        with patch.object(s, 'ROOT', self.root), patch.object(s, 'gate', return_value=self.current) as gate, patch.object(s, 'verify', side_effect=RuntimeError('backup unavailable')):
            self.assertEqual(s.execute(True)['state'], 'PARTIAL_REQUIRES_RECONCILIATION')
            self.assertEqual(gate.call_count, 1)

    def test_lost_server_ack_remains_intent_and_reconciles_without_redeletion(self):
        with patch.object(s, 'ROOT', self.root), patch.object(s, 'gate', side_effect=[self.current, RuntimeError('lost ack')]), patch.object(s, 'verify', return_value=self.proof):
            self.assertEqual(s.execute(True)['state'], 'PARTIAL_REQUIRES_RECONCILIATION')
        journal = next((self.root / 'receipts').glob('*.json')); intent = json.loads(journal.read_text())
        self.assertEqual(intent['state'], 'VERIFIED_INTENT')
        ack = {'state': 'REMOVED', 'operationId': intent['operationId'], 'expected': self.candidate, 'recovery': self.proof}
        with patch.object(s, 'ROOT', self.root), patch.object(s, 'gate', side_effect=[self.current, ack]) as gate, patch.object(s, 'verify') as verify:
            self.assertEqual(s.execute(True)['state'], 'COMPLETED'); verify.assert_not_called()
            self.assertEqual(gate.call_count, 2)
        self.assertEqual(json.loads(journal.read_text())['state'], 'COMPLETED')

    def test_only_completed_receipts_export(self):
        (self.root / 'receipts').mkdir(); (self.root / 'observed.json').write_text('{}')
        for number, state in enumerate(['VERIFIED_INTENT', 'ABORTED', 'COMPLETED']):
            (self.root / 'receipts' / f'{number}.json').write_text(json.dumps({'state': state}))
        with patch.object(s, 'ROOT', self.root):
            self.assertEqual(s.export()['receipts'], [{'state': 'COMPLETED'}])

    def test_reader_rejects_remove_and_uses_server_observation(self):
        with self.assertRaises(ValueError): reader.validate({'mode': 'remove'})
        op = 'b' * 32
        intent = {'state': 'COMPLETED', 'operationId': op, 'candidate': self.candidate, 'recovery': self.proof, 'gateSha256': c.GATE_SHA256}
        server = Mock(common=c)
        server.run.return_value = {'receipts': [intent], 'observed': {'server': 'timestamp'}}
        server.ack_matches.return_value = True
        server.gate.side_effect = [{'state': 'REMOVED'}, {'permitted': True}]
        self.assertEqual(reader.request({'mode': 'local-check', 'operationId': op, 'observed': {'fake': 'old'}, 'expected': {}}, server), {'permitted': True})
        self.assertEqual(server.gate.call_args.args[0]['observed'], {'server': 'timestamp'})
        self.assertEqual(server.gate.call_args.args[0]['expected'], self.candidate)

    def test_recovery_rejects_arbitrary_paths_and_large_or_invalid_hashes(self):
        valid = dict(self.candidate)
        self.assertEqual(r.validate(valid), valid)
        for changed in [valid | {'path': '/etc/shadow'}, valid | {'path': '/uploads/2026/11/13/../abcd.mp4'}, valid | {'sha256': 'wrong'}, valid | {'bytes': True}, valid | {'bytes': 1024 ** 3}]:
            with self.assertRaises(ValueError): r.validate(changed)

    def test_pc_transport_has_no_server_remove_or_arbitrary_shell_route(self):
        with patch.object(c.subprocess, 'run') as child:
            for mode in ['remove', 'inspect', 'sudo']:
                with self.assertRaises(RuntimeError): c.remote(c.CONTABO, c.SERVER, {'mode': mode})
            child.assert_not_called()

    def test_pc_catchup_only_deletes_pinned_local_selection(self):
        (self.root / 'local-map.json').write_text(json.dumps([{'sha256': 'a' * 64, 'postId': 'p', 'resolvedPath': 'x', 'localAssetId': 'original', 'deleteEligible': True}]))
        op = 'b' * 32
        intent = {'state': 'COMPLETED', 'operationId': op, 'candidate': self.candidate, 'recovery': self.proof}
        exported = {'observed': {'public': 'old'}, 'receipts': [intent]}
        ack = {'state': 'REMOVED', 'operationId': op, 'expected': self.candidate, 'recovery': self.proof}
        with patch.object(c, 'ROOT', self.root), patch.object(c, 'remote', side_effect=[exported, ack, self.proof, {'permitted': True}]) as remote, patch.object(c, 'delete_local', return_value={'state': 'REMOVED', 'bytes': 4}) as remove:
            result = c.execute_local_only(True)
            self.assertEqual(result['serverRemoved'], 0); remove.assert_called_once()
            self.assertTrue(all(call.args[2].get('mode') != 'remove' for call in remote.call_args_list))
        local = json.loads((self.root / 'pc-receipts' / (op + '.json')).read_text())
        self.assertEqual(local['selectedLocal'][0]['localAssetId'], 'original')

    def test_pc_without_server_receipts_never_verifies_or_removes(self):
        (self.root / 'local-map.json').write_text('[]')
        with patch.object(c, 'ROOT', self.root), patch.object(c, 'remote', return_value={'observed': {}, 'receipts': []}) as remote, patch.object(c, 'delete_local') as remove:
            self.assertEqual(c.execute_local_only(True)['eligibleCount'], 0)
            self.assertEqual(remote.call_count, 1); remove.assert_not_called()

    def test_pc_retry_does_not_enroll_new_matching_paths(self):
        original = {'sha256': 'a' * 64, 'postId': 'p', 'resolvedPath': 'old', 'localAssetId': 'original', 'deleteEligible': True}
        added = original | {'resolvedPath': 'new', 'localAssetId': 'newly-added'}
        (self.root / 'local-map.json').write_text(json.dumps([original, added]))
        op = 'b' * 32; (self.root / 'pc-receipts').mkdir()
        local = {'state': 'LOCAL_PENDING', 'operationId': op, 'candidate': self.candidate, 'recovery': self.proof, 'selectedLocal': [original]}
        (self.root / 'pc-receipts' / (op + '.json')).write_text(json.dumps(local))
        server = {'state': 'COMPLETED', 'operationId': op, 'candidate': self.candidate, 'recovery': self.proof}
        responses = [{'observed': {}, 'receipts': [server]}, {'state': 'REMOVED', 'operationId': op, 'expected': self.candidate, 'recovery': self.proof}, self.proof, {'permitted': True}]
        with patch.object(c, 'ROOT', self.root), patch.object(c, 'remote', side_effect=responses), patch.object(c, 'delete_local', return_value={'state': 'REMOVED', 'bytes': 4}) as remove:
            self.assertEqual(c.execute_local_only(True)['state'], 'COMPLETED')
            remove.assert_called_once(); self.assertEqual(remove.call_args.args[0]['localAssetId'], 'original')

    def test_pc_delete_ack_loss_records_unconfirmed_absence_without_redeleting(self):
        entry = {'sha256': 'a' * 64, 'postId': 'p', 'resolvedPath': str(self.root / 'removed.mp4'), 'localAssetId': 'original', 'deleteEligible': True}
        intent = {'localPending': 'original', 'local': []}
        with patch.object(c, 'delete_local') as remove:
            result = c.clean_local([entry], self.candidate, intent, self.root / 'journal.json')
            remove.assert_not_called()
        self.assertEqual(result[0]['state'], 'REMOVED_UNCONFIRMED'); self.assertEqual(result[0]['bytes'], 0)
        with patch.object(c, 'delete_local') as remove:
            c.clean_local([entry], self.candidate, intent, self.root / 'journal.json')
            remove.assert_not_called()


if __name__ == '__main__': unittest.main()
