import copy
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orchestrator import model_policy as m
from orchestrator import scheduler as s
from orchestrator import benchmark as b


class ModelPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.cli = self.base / 'pkg/bin/codebuddy'
        self.cli.parent.mkdir(parents=True)
        self.cli.write_text('fixture')
        s.write_json(self.cli.parent.parent / 'package.json', {'version': 'test'})
        (self.base / 'scheduler.py').write_text('fixture scheduler')
        self.evidence = self.base / 'catalog.json'
        self.catalog = {'source_kind': 'cli_acp_account_catalog', 'verified_at': s.now(), 'cli_version': 'test',
                        'models': {mid: [{'_meta': {'credits': 'x' + rate + ' credits'}}]
                                   for mid, rate in [('deepseek-v4.1-flash', '0.11'), ('minimax-m3.1-flash', '0.08')]}}
        s.write_json(self.evidence, self.catalog)
        self.models = self.base / 'models.json'
        self.config = {'max_credit_multiplier': '0.2', 'evidence_valid_hours': 24,
                       'primary_model': m.PRIMARY, 'fallback_model': m.FALLBACK,
                       'fallback_model_verified': True, 'max_technical_retries': 1,
                       'models': {mid: {'credit_multiplier': rate, 'rate_evidence': 'catalog.json',
                                       'rate_evidence_sha256': m.sha(self.evidence),
                                       'available_verified': True, 'headless_verified': True}
                                  for mid, rate in [('deepseek-v4.1-flash', '0.11'), ('minimax-m3.1-flash', '0.08')]}}
        for mid, entry in self.config['models'].items():
            entry['availability_evidence'] = mid + '.probe.json'
            s.write_json(self.base / entry['availability_evidence'], {
                'state': 'succeeded', 'model_id': mid, 'agent_session_id': 'probe-session',
                'selection': {'rate_verified_at': self.catalog['verified_at']},
                'consumption': {'observed_model_ids': [mid]}})
        self.save()
        self.policy = m.ModelPolicy(self.models, self.cli)

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        s.write_json(self.models, self.config)

    def test_allowed_and_manual(self):
        self.assertEqual(self.policy.choose()['model_id'], m.PRIMARY)
        self.assertEqual(self.policy.choose('deepseek-v4.1-flash')['credit_multiplier'], '0.11')

    def test_boundary_strictly_less_and_unknown(self):
        for rate, kind in [('0.2', 'credit_limit_exceeded'), ('0.20000001', 'credit_limit_exceeded'),
                           ('9', 'credit_limit_exceeded'), (None, 'credit_multiplier_unknown'),
                           ('NaN', 'credit_multiplier_unknown'), ('Infinity', 'credit_multiplier_unknown'),
                           ('-1', 'credit_multiplier_unknown')]:
            self.config['models']['deepseek-v4.1-flash']['credit_multiplier'] = rate
            self.save()
            with self.assertRaises(m.PolicyError) as cm:
                self.policy.choose('deepseek-v4.1-flash')
            self.assertEqual(cm.exception.kind, kind)

    def test_no_candidate_stops(self):
        for entry in self.config['models'].values():
            entry['credit_multiplier'] = None
        self.save()
        with self.assertRaises(m.PolicyError) as cm:
            self.policy.choose()
        self.assertEqual(cm.exception.kind, 'credit_multiplier_unknown')

    def test_unknown_id_even_if_in_config(self):
        self.config['models']['expensive'] = copy.deepcopy(next(iter(self.config['models'].values())))
        self.save()
        with self.assertRaises(m.PolicyError) as cm:
            self.policy.choose('expensive')
        self.assertEqual(cm.exception.kind, 'model_not_whitelisted')

    def test_invalid_threshold_is_rejected(self):
        self.config['max_credit_multiplier'] = 'NaN'
        self.save()
        with self.assertRaises(m.PolicyError):
            self.policy.choose()

    def test_evidence_stale_and_version_changes(self):
        for timestamp, version in [(datetime.now(timezone.utc) - timedelta(hours=25), 'test'),
                                   (datetime.now(timezone.utc), 'different')]:
            self.catalog.update(verified_at=timestamp.isoformat(), cli_version=version)
            s.write_json(self.evidence, self.catalog)
            for entry in self.config['models'].values():
                entry['rate_evidence_sha256'] = m.sha(self.evidence)
            self.save()
            with self.assertRaises(m.PolicyError) as cm:
                self.policy.choose('deepseek-v4.1-flash')
            self.assertEqual(cm.exception.kind, 'rate_evidence_stale')

    def test_evidence_tamper_and_rate_mismatch(self):
        self.catalog['models']['deepseek-v4.1-flash'][0]['_meta']['credits'] = 'x0.3 credits'
        s.write_json(self.evidence, self.catalog)
        with self.assertRaises(m.PolicyError):
            self.policy.choose('deepseek-v4.1-flash')
        self.config['models']['deepseek-v4.1-flash']['rate_evidence_sha256'] = m.sha(self.evidence)
        self.save()
        with self.assertRaises(m.PolicyError):
            self.policy.choose('deepseek-v4.1-flash')

    def test_headless_not_verified(self):
        self.config['models']['deepseek-v4.1-flash']['headless_verified'] = False
        self.save()
        with self.assertRaises(m.PolicyError):
            self.policy.choose('deepseek-v4.1-flash')
        self.assertTrue(self.policy.verified('deepseek-v4.1-flash', headless=False))

    def test_boolean_without_probe_not_sufficient(self):
        (self.base / self.config['models']['deepseek-v4.1-flash']['availability_evidence']).unlink()
        with self.assertRaises(m.PolicyError) as cm:
            self.policy.choose('deepseek-v4.1-flash')
        self.assertEqual(cm.exception.kind, 'model_unavailable')

    def test_benchmark_cannot_override_fixed_priority(self):
        report = {'recommendation': m.FALLBACK, 'valid_for_routing': True,
                  'scheduler_sha256': m.sha(Path(s.__file__)),
                  'policy_rate_signature': self.policy.rate_signature(), 'finished_at': s.now(),
                  'recommendation_reason': 'fixture score'}
        (self.base / 'benchmark').mkdir()
        s.write_json(self.base / 'benchmark/latest.json', report)
        self.assertEqual(self.policy.choose()['model_id'], 'deepseek-v4.1-flash')
        report['scheduler_sha256'] = 'stale'
        s.write_json(self.base / 'benchmark/latest.json', report)
        self.assertEqual(self.policy.choose()['model_id'], m.PRIMARY)

    def test_poor_correctness_is_not_provisional_default(self):
        (self.base / 'benchmark').mkdir()
        report = {'recommendation': None, 'valid_for_routing': False,
                  'scheduler_sha256': m.sha(Path(s.__file__)),
                  'policy_rate_signature': self.policy.rate_signature(), 'finished_at': s.now(),
                  'models': {'minimax-m3.1-flash': {'distinct_tasks': 10, 'final_success_rate': .2, 'quality_rate': .2}}}
        s.write_json(self.base / 'benchmark/latest.json', report)
        self.assertEqual(self.policy.choose()['model_id'], 'deepseek-v4.1-flash')

    def service(self):
        service = s.Scheduler(self.base / 'jobs', cli=self.cli, models=self.models)
        job = service.jobs / 'unitjob'
        job.mkdir(parents=True, exist_ok=True)
        (job / 'agent-cwd').mkdir(exist_ok=True)
        (job / 'workspace/.git').mkdir(parents=True, exist_ok=True)
        s.write_json(job / 'baseline.json', {})
        s.write_json(job / 'clean-git.json', {})
        import shutil
        shutil.copytree(job / 'workspace', job / 'clean-workspace', dirs_exist_ok=True)
        return service, job

    def response(self, mid):
        return json.dumps([{'type': 'result', 'is_error': False, 'session_id': 'test-session',
                            'model': mid, 'result': '{"changes":[]}'}])

    def test_first_and_rework_explicitly_pin_model(self):
        service, job = self.service()
        calls = []
        def command(job, label, argv, *args, **kwargs):
            mid = argv[argv.index('--model') + 1]
            calls.append(argv)
            return {'exit_code': 0, 'duration_seconds': 1}, self.response(mid), ''
        with patch.object(service, 'command', side_effect=command):
            service.call_agent(job, {}, 1, 'task')
            service.call_agent(job, {}, 2, 'rework')
        self.assertEqual(len(calls), 2)
        for argv in calls:
            self.assertEqual(argv[argv.index('--model') + 1], m.PRIMARY)
            self.assertNotIn('--fallback-model', argv)
            self.assertNotIn('--dangerously-skip-permissions', argv)

    def test_only_eligible_fallback(self):
        service, job = self.service()
        used = []
        def command(job, label, argv, *args, **kwargs):
            mid = argv[argv.index('--model') + 1]
            used.append(mid)
            if len(used) == 1:
                return {'exit_code': 1, 'duration_seconds': 1}, '', 'model unavailable 503'
            return {'exit_code': 0, 'duration_seconds': 1}, self.response(mid), ''
        with patch.object(service, 'command', side_effect=command):
            service.call_agent(job, {}, 1, 'task')
        self.assertEqual(used, [m.PRIMARY, m.FALLBACK])
        # A now-expensive backup must never execute.
        self.config['models'][m.FALLBACK]['credit_multiplier'] = '0.2'
        self.save()
        service.active_model = None  # New task; run() clears this in production.
        used.clear()
        with patch.object(service, 'command', side_effect=command):
            with self.assertRaises(s.Failure) as cm:
                service.call_agent(job, {}, 1, 'task')
        self.assertEqual(cm.exception.kind, 'fallback_unavailable')
        self.assertEqual(used, [m.PRIMARY])

    def test_manual_no_fallback_and_model_timeout_distinct(self):
        service, job = self.service()
        service.manual_model = 'deepseek-v4.1-flash'
        with patch.object(service, 'command', side_effect=s.Failure('timeout', 'injected')) as call:
            with self.assertRaises(s.Failure) as cm:
                service.call_agent(job, {}, 1, 'task')
        self.assertEqual(cm.exception.kind, 'timeout')
        self.assertEqual(call.call_count, 1)

    def test_overlimit_reaches_no_process(self):
        service, job = self.service()
        for entry in self.config['models'].values():
            entry['credit_multiplier'] = '0.2'
        self.save()
        with patch.object(service, 'command') as command:
            with self.assertRaises(s.Failure):
                service.call_agent(job, {}, 1, 'task')
            command.assert_not_called()
        with patch('orchestrator.scheduler.subprocess.Popen') as popen:
            with self.assertRaises(s.Failure):
                service.command(job, 'agent', [sys.executable, '--model', 'deepseek-v4.1-flash'], job, 1, agent=True)
            popen.assert_not_called()

    def test_identity_mismatch_stops(self):
        service, job = self.service()
        with patch.object(service, 'command', return_value=({'exit_code': 0, 'duration_seconds': 1},
                         self.response('expensive-model'), '')):
            with self.assertRaises(s.Failure) as cm:
                service.call_agent(job, {}, 1, 'task')
        self.assertEqual(cm.exception.kind, 'model_identity_mismatch')

    def test_cost_not_invented(self):
        value = m.telemetry(json.dumps([{'type': 'result', 'usage': {'input_tokens': 10},
                                       'total_cost_usd': 0}]), 'deepseek-v4.1-flash')
        self.assertIsNone(value['credits'])
        self.assertEqual(value['credits_kind'], 'unavailable')

    def test_score_reproducible_and_missing_cost_stays_missing(self):
        rows = []
        for mid in ('deepseek-v4.1-flash', 'minimax-m3.1-flash'):
            for i in range(10):
                rows.append({'model_id': mid, 'case_id': str(i), 'category': 'feature',
                             'metrics': {'success': True, 'first_pass': True, 'test_passed': 3,
                                         'test_fraction': 1, 'quality': 1, 'reworks': 0, 'seconds': 30,
                                         'timeout': False, 'relative_cost_proxy': 100, 'token_total': 100}})
        result = b.summarize(rows)
        x = result['deepseek-v4.1-flash']
        self.assertAlmostEqual(x['score'], 99.0)
        self.assertEqual(x['score'], sum(x['weighted_components'].values()))
        self.assertIsNone(b.recommendation(result, rows)[0])
        for row in rows:
            row['metrics']['relative_cost_proxy'] = None
        self.assertIsNone(b.summarize(rows)['deepseek-v4.1-flash']['score'])

    def test_estimated_cost_cannot_reverse_negative_quality_evidence(self):
        rows = []
        for mid, seconds, cost in [('deepseek-v4.1-flash', 10, 200), ('minimax-m3.1-flash', 50, 100)]:
            for cid in ['A1','A2','B1','B2','C1','C2','D1','D2','E1','E2']:
                for repeat in range(3):
                    rows.append({'model_id': mid, 'case_id': cid, 'category': 'feature',
                                 'metrics': {'success': True, 'first_pass': True, 'test_passed': 3,
                                             'test_fraction': 1, 'quality': 1, 'reworks': 0, 'seconds': seconds,
                                             'timeout': False, 'relative_cost_proxy': cost, 'token_total': 100}})
        scores = b.summarize(rows)
        self.assertGreater(scores['minimax-m3.1-flash']['score'], scores['deepseek-v4.1-flash']['score'])
        self.assertIsNone(b.recommendation(scores, rows)[0])


if __name__ == '__main__':
    unittest.main()
