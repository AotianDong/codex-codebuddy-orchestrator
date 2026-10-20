import json
from pathlib import Path
import unittest
from unittest.mock import patch
from orchestrator import model_policy as m, scheduler as s, config
from tests.unit.test_model_policy import ModelPolicyTests as _Fixture


class PriorityRoutingTests(unittest.TestCase):
    setUp = _Fixture.setUp
    tearDown = _Fixture.tearDown
    save = _Fixture.save
    service = _Fixture.service
    response = _Fixture.response

    def invoke(self, outcomes, attempt=1):
        service, job = self.service()
        used = []
        def command(job, label, argv, *args, **kwargs):
            mid = argv[argv.index('--model') + 1]
            used.append(mid)
            answer = outcomes[len(used) - 1]
            if isinstance(answer, Exception):
                raise answer
            return {'exit_code': 0, 'duration_seconds': 1}, self.response(mid), ''
        with patch.object(service, 'command', side_effect=command):
            try:
                service.call_agent(job, {}, attempt, 'task')
            except s.Failure as exc:
                return service, used, exc.kind
        return service, used, None

    def test_fixed_primary_ignores_cheapest_default(self):
        self.config['default_model'] = m.FALLBACK
        self.save()
        self.assertEqual(self.policy.choose()['model_id'], m.PRIMARY)

    def test_disallowed_third_model_and_raised_limit(self):
        for key, value in [('primary_model', 'other'), ('fallback_model', 'other'),
                           ('max_credit_multiplier', '0.5'), ('max_technical_retries', 99)]:
            original = self.config.get(key)
            self.config[key] = value
            self.save()
            with self.assertRaises(m.PolicyError):
                self.policy.choose()
            self.config[key] = original

    def test_fallback_disabled_stops_after_primary_service_failure(self):
        for configured, verified in [(None, False), (m.FALLBACK, False)]:
            self.config.update(fallback_model=configured, fallback_model_verified=verified)
            self.save()
            _, used, error = self.invoke([s.Failure('model_service_error', 'HTTP 503')])
            self.assertEqual(used, [m.PRIMARY])
            self.assertEqual(error, 'fallback_unavailable')

    def test_only_explicit_service_failures_switch(self):
        for reason in sorted(m.SERVICE_FAILURES):
            _, used, error = self.invoke([s.Failure(reason, 'injected'), 'ok'])
            self.assertEqual(used, [m.PRIMARY, m.FALLBACK])
            self.assertIsNone(error)

    def test_non_service_errors_never_switch_or_retry(self):
        for reason in ('permission_denied', 'environment_error', 'cli_failed', 'json_parse_failed',
                       'agent_error', 'scope_denied', 'test_failed', 'timeout', 'execution_timeout',
                       'termination_unconfirmed', 'resource_limit', 'internal_error'):
            _, used, error = self.invoke([s.Failure(reason, 'injected')])
            self.assertEqual(used, [m.PRIMARY], reason)
            self.assertEqual(error, reason)

    def test_persistent_remote_timeout_retries_once_then_switches(self):
        service, used, error = self.invoke([s.Failure('model_timeout', 'remote'),
                                           s.Failure('model_timeout', 'remote'), 'ok'])
        self.assertEqual(used, [m.PRIMARY, m.PRIMARY, m.FALLBACK])
        self.assertIsNone(error)
        self.assertEqual([x['call_kind'] for x in service.model_calls], ['initial','technical_retry','fallback'])
        self.assertEqual(len({x['requested_session_id'] for x in service.model_calls}), 3)

    def test_recovered_timeout_does_not_switch(self):
        _, used, error = self.invoke([s.Failure('model_timeout', 'remote'), 'ok'])
        self.assertEqual(used, [m.PRIMARY, m.PRIMARY])
        self.assertIsNone(error)

    def test_zero_retry_budget_allows_remote_timeout_fallback(self):
        self.config['max_technical_retries'] = 0
        self.save()
        _, used, error = self.invoke([s.Failure('model_timeout', 'remote'), 'ok'])
        self.assertEqual(used, [m.PRIMARY, m.FALLBACK])
        self.assertIsNone(error)

    def test_no_third_model_or_switch_back(self):
        _, used, error = self.invoke([s.Failure('model_unavailable', 'remote'),
                                     s.Failure('model_unavailable', 'remote')])
        self.assertEqual(used, [m.PRIMARY, m.FALLBACK])
        self.assertEqual(error, 'model_unavailable')

    def test_successful_fallback_remains_sticky_for_rework(self):
        service, job = self.service()
        used = []
        def command(job, label, argv, *args, **kwargs):
            mid = argv[argv.index('--model') + 1]
            used.append(mid)
            if len(used) == 1:
                raise s.Failure('model_unavailable', 'remote')
            return {'exit_code': 0, 'duration_seconds': 1}, self.response(mid), ''
        with patch.object(service, 'command', side_effect=command):
            service.call_agent(job, {}, 1, 'initial')
            service.call_agent(job, {}, 2, 'failed test feedback')
        self.assertEqual(used, [m.PRIMARY, m.FALLBACK, m.FALLBACK])

    def test_fallback_restarts_partial_workspace_and_preserves_archive(self):
        service, job = self.service()
        app = job / 'workspace/app.py'
        app.write_text('baseline')
        (job / 'clean-workspace/app.py').write_text('baseline')
        s.write_json(job / 'baseline.json', s.inventory(job / 'workspace'))
        task = {'requirements': ['fix app'], 'allowed_files': ['app.py'], 'context_files': ['app.py'],
                'forbidden_operations': ['never edit tests']}
        used = []
        def command(job, label, argv, cwd, timeout, prompt, **kwargs):
            mid = argv[argv.index('--model') + 1]
            used.append(mid)
            if len(used) == 2:
                raise s.Failure('model_service_error', 'remote')
            if len(used) == 3:
                self.assertEqual(app.read_text(), 'baseline')
                self.assertNotIn('partial implementation', prompt)
                self.assertEqual(len(list(job.glob('workspace-before-switch-*'))), 1)
            return {'exit_code': 0, 'duration_seconds': 1}, self.response(mid), ''
        with patch.object(service, 'command', side_effect=command):
            service.call_agent(job, task, 1, 'initial')
            app.write_text('partial implementation')
            service.call_agent(job, task, 2, 'rework partial implementation')
        self.assertEqual(used, [m.PRIMARY, m.PRIMARY, m.FALLBACK])
        archive = next(job.glob('workspace-before-switch-*'))
        self.assertEqual((archive / 'app.py').read_text(), 'partial implementation')

    def test_unexpected_files_or_git_changes_stop_before_fallback(self):
        for name in ('app.py', '.git/config'):
            service, job = self.service()
            used = []
            def command(job, label, argv, *args, **kwargs):
                used.append(argv)
                (job / 'workspace' / name).write_text('unexpected')
                raise s.Failure('model_unavailable', 'remote')
            with patch.object(service, 'command', side_effect=command):
                with self.assertRaises(s.Failure) as cm:
                    service.call_agent(job, {}, 1, 'initial')
            self.assertEqual(cm.exception.kind, 'workspace_state_uncertain')
            self.assertEqual(len(used), 1)

    def test_cli_does_not_enable_implicit_fallback(self):
        service, job = self.service()
        argv = [str(self.cli), '--model', m.PRIMARY, '--fallback-model', m.FALLBACK]
        with patch('orchestrator.scheduler.subprocess.Popen') as start:
            with self.assertRaises(s.Failure) as cm:
                service.command(job, 'agent', argv, job, 1, agent=True)
            start.assert_not_called()
        self.assertEqual(cm.exception.kind, 'policy_invalid')

    def test_error_classification_does_not_scan_successful_code_or_bare_numbers(self):
        for text, kind in [('HTTP 429 Too Many Requests', 'model_rate_limited'),
                           ('HTTP 503 Service Unavailable', 'model_service_error'),
                           ('HTTP 502 Bad Gateway', 'model_service_error'),
                           ('model request timed out', 'model_timeout'),
                           ('HTTP 504 Gateway Timeout', 'model_timeout'),
                           ('model service failure', 'model_service_error'),
                           ('permission denied HTTP 503', 'permission_denied')]:
            self.assertEqual(m.classify_cli('', text, 1), kind)
        self.assertEqual(m.classify_cli('', 'local validation failed at line 503', 1), 'cli_failed')
        self.assertEqual(m.classify_cli('', 'task failed to implement rate_limit()', 1), 'cli_failed')
        ok = json.dumps([{'type':'result','is_error':False,'result':'model unavailable; HTTP 503'}])
        self.assertIsNone(m.classify_cli(ok, '', 0))
        self.assertIsNone(m.classify_cli(ok, 'previous request HTTP 503', 0))
        self.assertIsNone(m.classify_cli('invalid JSON with 503', '', 0))

    def test_real_json_parse_failure_is_not_a_model_identity_failure(self):
        service, job = self.service()
        with patch.object(service, 'command', return_value=({'exit_code':0,'duration_seconds':1}, '{broken', '')) as cmd:
            with self.assertRaises(s.Failure) as cm:
                service.call_agent(job, {}, 1, 'task')
        self.assertEqual(cm.exception.kind, 'json_parse_failed')
        self.assertEqual(cmd.call_count, 1)

    def test_effective_config_limits(self):
        path = self.base / 'config.yaml'
        good = {'candidate_models': [m.PRIMARY,m.FALLBACK]}
        s.write_json(path, good)
        loaded = config.load(path)
        self.assertEqual(loaded['primary_model'], m.PRIMARY)
        self.assertIsNone(loaded['fallback_model'])
        self.assertEqual(loaded['max_technical_retries'], 1)
        for key, val in [('fallback_model','third'), ('primary_model',m.FALLBACK),
                         ('max_credit_multiplier','0.5'), ('max_technical_retries',-1),
                         ('candidate_models',[m.PRIMARY,'third'])]:
            s.write_json(path, {**good,key:val})
            with self.assertRaises(ValueError):
                config.load(path)


del _Fixture
