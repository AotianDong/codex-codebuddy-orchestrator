"""Public CLI around the migrated scheduler and model verification pipeline."""
import argparse
import json
from pathlib import Path
import sys
from . import config, scheduler as s
from .model_policy import PolicyError, ModelPolicy
from .runtime import discover_cli

def service(cfg, model=None):
    node, cli = discover_cli()
    policy_file = cfg['_state'] / 'models.json'
    if policy_file.exists():
        policy = s.read_json(policy_file)
        policy['max_credit_multiplier'] = str(cfg['max_credit_multiplier'])
        policy['default_model'] = cfg['default_model']
        for key in ('primary_model', 'fallback_model', 'fallback_model_name',
                    'fallback_model_verified', 'max_technical_retries'):
            policy[key] = cfg[key]
        policy['models'] = {k: v for k, v in policy['models'].items() if k in cfg['candidate_models']}
        if not cfg['benchmark_enabled']:
            policy['benchmark_report'] = 'benchmark-disabled.json'
        else:
            policy['benchmark_report'] = 'benchmark/latest.json'
        s.write_json(policy_file, policy)
    return s.Scheduler(cfg['_jobs'], cfg['node_path'] or node, cfg['codebuddy_cli'] or cli, policy_file, model)

def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path)
    p.add_argument('--model')
    subs = p.add_subparsers(dest='action', required=True)
    for name in ('submit', 'execute'):
        subs.add_parser(name).add_argument('manifest', type=Path)
    for name in ('run', 'status', 'progress', 'result', 'diff'):
        subs.add_parser(name).add_argument('task_id')
    for name in ('doctor', 'models-refresh', 'models-probe', 'models-status', 'history'):
        subs.add_parser(name)
    b = subs.add_parser('benchmark')
    b.add_argument('--single-repeat', action='store_true')
    b.add_argument('--prepare', action='store_true')
    a = p.parse_args(argv)
    try:
        cfg = config.load(a.config)
        svc = service(cfg, a.model)
        if a.action == 'doctor':
            from .doctor import inspect
            result = inspect(cfg)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result['ready_for_execution'] else 2
        if a.action == 'models-refresh':
            from .audit_models import discover
            from .manage_models import configure
            catalog = cfg['_state'] / 'catalog'
            discover(svc.node, svc.cli, catalog)
            configure(catalog / 'catalog.json', svc.policy.path, cfg['max_credit_multiplier'], cfg['default_model'])
            # Explicit whitelist filtering also applies before any probe.
            service(cfg)
        elif a.action == 'models-probe':
            from .manage_models import probe
            probe(svc.policy.path, svc.node, svc.cli)
            eligible, rejected = svc.policy.eligible()
            if not eligible:
                raise PolicyError('no_compliant_model', json.dumps(rejected))
        elif a.action == 'models-status':
            ok, bad = svc.policy.eligible()
            print(json.dumps({'eligible': ok, 'rejected': bad}, ensure_ascii=False, indent=2))
            return 0 if ok else 2
        elif a.action == 'history':
            from .evaluator import summarize_history
            print(json.dumps(summarize_history(cfg['_state'] / 'history'), ensure_ascii=False, indent=2))
        elif a.action == 'benchmark':
            if not cfg['benchmark_enabled']:
                raise ValueError('Benchmark disabled in config')
            from . import prepare_benchmarks as prep, benchmark as bench
            bench_dir = cfg['_state'] / 'benchmark'
            prep.SUITE = bench_dir / 'suite'
            if a.prepare:
                prep.main()
            else:
                bench.run_suite(svc.policy.path, not a.single_repeat, node=svc.node, cli=svc.cli,
                                jobs=svc.jobs, bench_dir=bench_dir)
        elif a.action in ('submit', 'execute', 'run'):
            if a.action != 'run':
                task = s.read_json(a.manifest)
                task.setdefault('agent_timeout_seconds', cfg['agent_timeout_seconds'])
                task.setdefault('max_reworks', cfg['max_reworks'])
                if not task.get('tests'):
                    task['tests'] = cfg['test_commands']
                # Config is a maximum budget, a manifest may further tighten it.
                task['max_reworks'] = min(task['max_reworks'], cfg['max_reworks'])
                task['agent_timeout_seconds'] = min(task['agent_timeout_seconds'], cfg['agent_timeout_seconds'])
                import tempfile
                with tempfile.TemporaryDirectory() as temporary:
                    manifest = Path(temporary) / 'task.json'
                    s.write_json(manifest, task)
                    task_id = svc.submit(manifest)
                print(json.dumps({'task_id': task_id, 'state': 'queued'}), flush=True)
            else:
                task_id = a.task_id
            if a.action != 'submit':
                report = svc.run(task_id)
                from .evaluator import record_result
                record_result(report, cfg['_state'] / 'history', origin='real_task')
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0 if report['state'] == 'succeeded' else 2
        else:
            filename = {'status': 'status.json', 'progress': 'events.jsonl', 'result': 'report.json', 'diff': 'change.diff'}[a.action]
            print((svc.locate(a.task_id) / filename).read_text('utf-8'))
        return 0
    except (s.Failure, PolicyError) as e:
        print(json.dumps({'state': 'failed', 'failure_kind': e.kind, 'detail': e.detail}, ensure_ascii=False))
        return 2
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps({'state': 'failed', 'failure_kind': 'configuration_or_environment_error', 'detail': str(e)}, ensure_ascii=False))
        return 2
