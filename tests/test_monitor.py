import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('monitor', Path(__file__).parents[1] / 'ops/item79-monitor.py')
monitor = importlib.util.module_from_spec(spec); spec.loader.exec_module(monitor)


class MonitorTest(unittest.TestCase):
    def test_transient_failure_does_not_alert(self):
        state = {}
        self.assertEqual(monitor.health_transition(state, False, 1), [])
        self.assertEqual(monitor.health_transition(state, False, 2), [])
        self.assertEqual(monitor.health_transition(state, True, 3), [])

    def test_outage_is_deduped_and_recovery_requires_two_successes(self):
        state = {}
        events = []
        for stamp in range(5):
            events += monitor.health_transition(state, False, stamp)
        self.assertEqual([event['kind'] for event in events], ['site_down'])
        self.assertEqual(monitor.health_transition(state, True, 6), [])
        self.assertEqual(monitor.health_transition(state, True, 7)[0]['kind'], 'site_recovered')
        self.assertEqual(monitor.health_transition(state, True, 8), [])

    def test_deployment_failure_filters_old_other_branch_and_seen_runs(self):
        template = {'id': 1, 'head_branch': 'main', 'event': 'push', 'conclusion': 'failure', 'created_at': '2026-11-13T05:00:00Z', 'html_url': 'https://github.com/lsk7209/postiz-item79/actions/runs/1'}
        self.assertEqual(len(monitor.failed_deploys({'workflow_runs': [template]}, '2026-11-13T04:00:00Z', [])), 1)
        for changed in [dict(template, head_branch='other'), dict(template, conclusion='success'), dict(template, created_at='2026-01-01T00:00:00Z')]:
            self.assertEqual(monitor.failed_deploys({'workflow_runs': [changed]}, '2026-11-13T04:00:00Z', []), [])
        self.assertEqual(monitor.failed_deploys({'workflow_runs': [template]}, '2026-11-13T04:00:00Z', ['1']), [])

    def test_workflow_pagination_and_coverage_limit(self):
        with patch.object(monitor, 'read_json', side_effect=[{'total_count': 101, 'workflow_runs': [{'id': i} for i in range(100)]}, {'total_count': 101, 'workflow_runs': [{'id': 100}]}]) as fetch:
            self.assertEqual(len(monitor.workflow_runs('2026-11-13T00:00:00Z')), 101)
            self.assertIn('page=2', fetch.call_args.args[0])
        with patch.object(monitor, 'read_json', return_value={'total_count': 1000}):
            with self.assertRaises(RuntimeError):
                monitor.workflow_runs('2026-11-13T00:00:00Z')

    def test_api_failure_alert_is_deduped_and_cursor_preserved(self):
        state = {'seenRuns': [], 'githubScanSince': '2026-11-13T00:00:00Z'}
        with patch.object(monitor, 'workflow_runs', side_effect=RuntimeError):
            self.assertEqual(monitor.observe_deployments(state, state['githubScanSince'], 1000), [])
            self.assertEqual(monitor.observe_deployments(state, state['githubScanSince'], 1300)[0]['kind'], 'github_unavailable')
            self.assertEqual(monitor.observe_deployments(state, state['githubScanSince'], 1600), [])
        self.assertEqual(state['githubScanSince'], '2026-11-13T00:00:00Z')
        with patch.object(monitor, 'workflow_runs', return_value=[]):
            self.assertEqual(monitor.observe_deployments(state, state['githubScanSince'], 1900)[0]['kind'], 'github_recovered')

    def test_cursor_revisits_old_unfinished_run_until_completion(self):
        pending = {'id': 5, 'status': 'in_progress', 'created_at': '2026-11-13T01:00:00Z', 'head_branch': 'main', 'event': 'push'}
        state = {'seenRuns': []}
        now = int(monitor.datetime.datetime(2026, 11, 13, 5, tzinfo=monitor.datetime.timezone.utc).timestamp())
        with patch.object(monitor, 'workflow_runs', return_value=[pending]):
            monitor.observe_deployments(state, '2026-11-13T00:00:00Z', now)
        self.assertEqual(state['githubScanSince'], pending['created_at'])
        failed = dict(pending, status='completed', conclusion='failure', html_url='https://github.com/lsk7209/postiz-item79/actions/runs/5')
        with patch.object(monitor, 'workflow_runs', return_value=[failed]):
            events = monitor.observe_deployments(state, '2026-11-13T00:00:00Z', now + 300)
            self.assertEqual(events[0]['kind'], 'deploy_failed')
            self.assertEqual(monitor.observe_deployments(state, '2026-11-13T00:00:00Z', now + 600), [])
