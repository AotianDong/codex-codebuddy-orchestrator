import copy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from orchestrator import config, evaluator, scheduler as s, benchmark as b
from orchestrator.runtime import cli_command
from tests.unit.test_model_policy import ModelPolicyTests

ROOT = Path(__file__).resolve().parents[2]

class NewPolicyTests(ModelPolicyTests):
    # Reuse fixture creation without rediscovering inherited regression cases.
    def test_configurable_threshold_and_explicit_default(self):
        self.config['max_credit_multiplier'] = '0.5'
        self.config['default_model'] = 'deepseek-v4.1-flash'
        self.save()
        self.assertEqual(self.policy.choose()['model_id'], 'deepseek-v4.1-flash')
        self.config['max_credit_multiplier'] = '0.08'
        self.save()
        with self.assertRaises(Exception):
            self.policy.choose()

    def test_missing_model_identity_stops(self):
        service, job = self.service()
        response = json.dumps([{'type':'result','is_error':False,'session_id':'x','result':'{"changes":[]}'}])
        with patch.object(service, 'command', return_value=({'exit_code':0,'duration_seconds':1}, response, '')):
            with self.assertRaises(s.Failure) as error:
                service.call_agent(job, {}, 1, 'prompt')
        self.assertEqual(error.exception.kind, 'model_identity_mismatch')

class PackagingTests(unittest.TestCase):
    def test_history_is_persisted_without_paths_or_fake_success(self):
        with tempfile.TemporaryDirectory() as d:
            report={'task_id':'a'*32,'state':'needs_review','source_unchanged':True,
                    'acceptance':[{'verdict':'manual_review_required'}],
                    'attempts':[{'tests':[{'exit_code':0}]}],
                    'model_calls':[{'model_id':'minimax-m3.1-flash','duration_seconds':2}]}
            item=evaluator.record_result(report,d)
            self.assertFalse(item['success'])
            self.assertNotIn('repository', item)
            summary=evaluator.summarize_history(d)
            self.assertEqual(summary['models']['minimax-m3.1-flash']['success_rate'],0)
            self.assertIsNone(summary['models']['minimax-m3.1-flash']['actual_credits'])

    def test_config_rejects_invalid_values_and_keeps_relative_logs(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'config.yaml'
            data=json.loads((ROOT/'config.example.yaml').read_text('utf-8'))
            # Example's comment is removed by installer, see config loader.
            for key,value in [('max_reworks',2),('max_credit_multiplier','NaN'),('candidate_models',[])]:
                bad=copy.deepcopy(data);bad[key]=value;s.write_json(path,bad)
                with self.assertRaises((ValueError,ArithmeticError)):
                    config.load(path)
            s.write_json(path,data)
            self.assertEqual(config.load(path)['_jobs'],(Path(d)/'jobs').resolve())

    def test_shell_shims_are_not_executed(self):
        with tempfile.TemporaryDirectory() as d:
            shim=Path(d)/'cli.cmd';shim.write_text('bad')
            with self.assertRaises(ValueError):cli_command('',str(shim))

    def test_metric_denominator_and_unpassed_acceptance(self):
        row=b.metrics({'state':'needs_review','source_unchanged':True,'attempts':[{'tests':[{'id':'x','exit_code':0}]}]},1)
        self.assertEqual(row['test_total'],1)
        self.assertFalse(row['success'])

    def test_public_scanner_detects_secret_and_personal_path(self):
        spec=importlib.util.spec_from_file_location('scan',ROOT/'scripts/scan_public.py')
        scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d);s.git(repo,'init','-q')
            (repo/'bad.txt').write_text('ghp_'+'a'*36+'\n'+'C:'+chr(92)+'Users'+chr(92)+'someone'+chr(92)+'private')
            result=scanner.scan(repo)
            self.assertEqual({x['kind'] for x in result['findings']},{'provider_token','personal_windows_path'})

# unittest discovers imported test classes too; keep only the two new methods here.
for _name in list(dir(NewPolicyTests)):
    if _name.startswith('test_') and _name not in NewPolicyTests.__dict__:
        setattr(NewPolicyTests,_name,None)
del ModelPolicyTests
