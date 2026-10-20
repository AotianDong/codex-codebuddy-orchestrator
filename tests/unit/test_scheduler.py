import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orchestrator import scheduler as s


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        (self.repo / 'app.py').write_text('def calculate(a,b):\n    return a+b\n')
        (self.repo / 'verify.py').write_text(
            'import app\nassert app.calculate(3,4) == 12\nprint("independent acceptance passed")\n')
        s.git(self.repo, 'init', '-q')
        s.git(self.repo, 'add', '--all')
        s.git(self.repo, '-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '-qm', 'initial')
        self.task = {'version': 1, 'repository': str(self.repo),
                     'requirements': ['calculate must multiply'], 'allowed_files': ['app.py'],
                     'context_files': ['app.py', 'verify.py'],
                     'forbidden_operations': ['Do not edit tests or the source repository'],
                     'acceptance': [{'id': 'product', 'description': 'Multiplication correct', 'test_ids': ['verify']}],
                     'tests': [{'id': 'verify', 'argv': ['$PYTHON', '-B', 'verify.py'], 'timeout_seconds': 10}]}
        self.service = s.Scheduler(self.base / 'jobs')
        # V1 regression tests use Agent stubs and must not depend on live billing.
        policy = patch.object(self.service.policy, 'choose', return_value={
            'model_id': 'deepseek-v4.1-flash', 'credit_multiplier': '0.11', 'reason': 'test fixture'})
        policy.start()
        self.addCleanup(policy.stop)
        self.original = s.source_fingerprint(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def submit(self):
        manifest = self.base / 'task.json'
        s.write_json(manifest, self.task)
        return self.service.submit(manifest)

    def fake_agent(self, bodies):
        def call(job, task, attempt, prompt):
            return 'actual-session-' + str(attempt), {'changes': [{'path': 'app.py', 'content': bodies[attempt - 1]}]}
        return call

    def execute(self, bodies):
        task_id = self.submit()
        with patch.object(self.service, 'call_agent', side_effect=self.fake_agent(bodies)):
            result = self.service.run(task_id)
        self.assertEqual(self.original, s.source_fingerprint(self.repo))
        return task_id, result

    def test_success_diff_and_logs(self):
        task_id, report = self.execute(['def calculate(a,b):\n    return a*b\n'])
        self.assertEqual(report['state'], 'succeeded')
        self.assertTrue(report['source_unchanged'])
        self.assertEqual(report['attempts'][0]['agent_session_id'], 'actual-session-1')
        self.assertEqual(report['attempts'][0]['tests'][0]['exit_code'], 0)
        self.assertEqual(report['changes'][0]['path'], 'app.py')
        self.assertIn('+    return a*b', (self.service.locate(task_id) / 'change.diff').read_text())

    def test_one_rework(self):
        task_id, report = self.execute(['def calculate(a,b):\n    return a+b\n',
                                        'def calculate(a,b):\n    return a*b\n'])
        self.assertEqual(report['state'], 'succeeded')
        self.assertEqual(len(report['attempts']), 2)
        self.assertEqual(report['attempts'][0]['tests'][0]['exit_code'], 1)
        self.assertTrue((self.service.locate(task_id) / 'rework.json').exists())

    def test_two_test_failures_are_terminal(self):
        _, report = self.execute(['def calculate(a,b):\n    return a+b\n'] * 2)
        self.assertEqual(report['failure_kind'], 'test_failed')
        self.assertEqual(len(report['attempts']), 2)

    def test_no_rework_setting(self):
        self.task['max_reworks'] = 0
        _, report = self.execute(['def calculate(a,b):\n    return a+b\n'])
        self.assertEqual(report['failure_kind'], 'test_failed')
        self.assertEqual(len(report['attempts']), 1)

    def test_timeout_permissions_and_json_stop_without_retry(self):
        for kind in ('timeout', 'permission_denied', 'json_parse_failed'):
            task_id = self.submit()
            with patch.object(self.service, 'call_agent', side_effect=s.Failure(kind, 'injected')) as call:
                report = self.service.run(task_id)
                self.assertEqual(report['failure_kind'], kind)
                self.assertEqual(call.call_count, 1)

    def test_real_test_process_timeout(self):
        self.task['tests'][0]['argv'] = ['$PYTHON', '-B', '-c', 'import time; time.sleep(30)']
        self.task['tests'][0]['timeout_seconds'] = 1
        task_id, report = self.execute(['def calculate(a,b):\n    return a*b\n'])
        self.assertEqual(report['failure_kind'], 'timeout')
        meta = s.read_json(self.service.locate(task_id) / 'test-1-verify.command.json')
        self.assertTrue(meta['timed_out'])

    def test_out_of_scope_not_written(self):
        task_id = self.submit()
        with patch.object(self.service, 'call_agent', return_value=('s', {'changes': [
                {'path': 'verify.py', 'content': 'print("FAKE PASS")'}]})):
            report = self.service.run(task_id)
        self.assertEqual(report['failure_kind'], 'scope_denied')
        ws = self.service.locate(task_id) / 'workspace'
        self.assertEqual((ws / 'verify.py').read_bytes(), (self.repo / 'verify.py').read_bytes())

    def test_parse_plain_text_is_not_success(self):
        values = ['Task complete, tests passed', '[]', '{', json.dumps([
            {'type': 'result', 'is_error': False, 'result': 'All tests passed!'}])]
        for value in values:
            with self.assertRaises(s.Failure) as cm:
                s.parse_agent(value)
            self.assertEqual(cm.exception.kind, 'json_parse_failed')
        session, value = s.parse_agent(json.dumps([{'type': 'result', 'is_error': False,
                             'session_id': 'session', 'result': '{"changes":[]}'}]))
        self.assertEqual(session, 'session')

    def test_permission_result(self):
        with self.assertRaises(s.Failure) as cm:
            s.parse_agent(json.dumps([{'type': 'result', 'is_error': True, 'result': 'permission denied'}]))
        self.assertEqual(cm.exception.kind, 'permission_denied')

    def test_agent_command_denied(self):
        task_id = self.submit()
        job = self.service.locate(task_id)
        with patch('orchestrator.scheduler.subprocess.Popen', side_effect=PermissionError('injected denial')):
            with self.assertRaises(s.Failure) as cm:
                self.service.command(job, 'denial', [sys.executable], self.repo, 10)
        self.assertEqual(cm.exception.kind, 'permission_denied')
        self.assertTrue(s.read_json(job / 'denial.command.json')['permission_denied'])

    def test_empty_acceptance_mapping_requires_review(self):
        self.task['acceptance'][0]['test_ids'] = []
        _, report = self.execute(['def calculate(a,b):\n    return a*b\n'])
        self.assertEqual(report['state'], 'needs_review')

    def test_replay_does_not_overwrite_report(self):
        task_id, report = self.execute(['def calculate(a,b):\n    return a*b\n'])
        with self.assertRaises(s.Failure):
            self.service.run(task_id)
        self.assertEqual(s.read_json(self.service.locate(task_id) / 'report.json'), report)

    def test_tampered_manifest(self):
        task_id = self.submit()
        job = self.service.locate(task_id)
        (job / 'task.json').write_text('{}')
        self.assertEqual(self.service.run(task_id)['failure_kind'], 'task_tampered')

    def test_dirty_source_rejected(self):
        (self.repo / 'app.py').write_text('# unsaved work')
        task_id = self.submit()
        self.assertEqual(self.service.run(task_id)['failure_kind'], 'repository_dirty')

    def test_paths_and_schema(self):
        for name in ('../escape', 'C:/file', 'x\\y', '.git/config', 'NUL', 'x/../z', 'z:stream', 'trailing.'):
            with self.assertRaises(s.Failure):
                s.safe_name(name)
        for key, value in [('max_reworks', 2), ('tests', []), ('repository', 'relative')]:
            task = copy.deepcopy(self.task)
            task[key] = value
            with self.assertRaises(s.Failure):
                s.validate_task(task)

    def test_replacement_preserves_crlf_and_bom(self):
        target = self.base / 'encoding.py'
        target.write_bytes(b'\xef\xbb\xbfline\r\n')
        self.assertEqual(s.replacement_bytes(target, 'new\n'), b'\xef\xbb\xbfnew\r\n')

    def test_tests_cannot_modify_workspace(self):
        self.task['tests'][0]['argv'] = ['$PYTHON', '-B', '-c',
            'from pathlib import Path; Path("app.py").write_text("# changed by test")']
        _, report = self.execute(['def calculate(a,b):\n    return a*b\n'])
        self.assertEqual(report['failure_kind'], 'test_mutated_workspace')

    def test_new_file_is_in_diff(self):
        self.task['allowed_files'].append('new.txt')
        task_id = self.submit()
        with patch.object(self.service, 'call_agent', return_value=('s', {'changes': [
            {'path': 'app.py', 'content': 'def calculate(a,b):\n    return a*b\n'},
            {'path': 'new.txt', 'content': 'new file\n'}]})):
            report = self.service.run(task_id)
        self.assertEqual(report['state'], 'succeeded')
        self.assertIn('new file mode', (self.service.locate(task_id) / 'change.diff').read_text())


if __name__ == '__main__':
    unittest.main()
