"""Recompute local evidence without inference. Raw records remain private."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from orchestrator import config, scheduler as s, benchmark as b

def verify_job(directory, maximum):
    task=s.read_json(directory/'task.json')
    report=s.read_json(directory/'report.json')
    baseline=s.read_json(directory/'source-before.json')
    after=s.read_json(directory/'source-after.json')
    checks={
        'source_unchanged': baseline==after and report['source_unchanged'] is True,
        'scope_valid': all(x['path'] in task['allowed_files'] for x in report['changes']),
        'at_most_one_rework': 1<=len(report['attempts'])<=2,
        'diff_exists': (directory/'change.diff').is_file(),
        'fixed_test_commands':True, 'explicit_model_and_identity':True,
        'cost_below_threshold':True,'no_permission_bypass':True,
        'acceptance_consistent':report['state']!='succeeded' or (
            bool(report['acceptance']) and all(x.get('verdict')=='passed' for x in report['acceptance'])
            and all(t.get('exit_code')==0 for t in report['attempts'][-1]['tests']))}
    tests={t['id']:t for t in task['tests']}
    for attempt in report['attempts']:
        for row in attempt['tests']:
            command=s.read_json(directory/row['command_log'])
            checks['fixed_test_commands'] &= command['argv']==tests[row['id']]['argv']
    for call in report['model_calls']:
        command=s.read_json(directory/(call['log_label']+'.command.json'))['argv']
        mid=call['model_id']
        checks['explicit_model_and_identity'] &= (
            command[command.index('--model')+1]==mid
            and command[command.index('--fallback-model')+1]==mid
            and (call['state']!='succeeded' or call['consumption']['observed_model_ids']==[mid]))
        checks['cost_below_threshold'] &= Decimal(call['credit_multiplier'])<Decimal(str(maximum))
        checks['no_permission_bypass'] &= not any(x in command for x in ('-y','--dangerously-skip-permissions','--serve'))
    if report['state']=='succeeded':
        checks['all_tests_executed']=set(t['id'] for t in report['attempts'][-1]['tests'])==set(tests)
    return checks

def verify_benchmark(report, jobs, maximum):
    rows=report['runs']
    checks={'scores_recompute':b.summarize(rows)==report['models'],
            'recommendation_recomputes':b.recommendation(report['models'],rows)[0]==report['recommendation'],
            'paired_conditions':True, 'all_job_evidence':True,
            'scheduler_matches':report['scheduler_sha256']==b.sha(ROOT/'src/orchestrator/scheduler.py')}
    models=set(report['models'])
    for cid in {x['case_id'] for x in rows}:
        pair=[x for x in rows if x['case_id']==cid]
        checks['paired_conditions'] &= (len({x['source_head'] for x in pair})==1
            and len({x['task_manifest_sha256'] for x in pair})==1
            and {x['model_id'] for x in pair}==models
            and len({sum(x['model_id']==m for x in pair) for m in models})==1)
    for row in rows:
        checks['all_job_evidence'] &= all(verify_job(jobs/row['task_id'],maximum).values())
    return checks

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--task-id')
    p.add_argument('--benchmark-report',type=Path)
    a=p.parse_args()
    cfg=config.load(a.config)
    result={}
    if a.task_id:
        # Validate the identifier before path traversal.
        svc=s.Scheduler(jobs=cfg['_jobs'])
        result['task']=verify_job(svc.locate(a.task_id),cfg['max_credit_multiplier'])
    if a.benchmark_report:
        result['benchmark']=verify_benchmark(s.read_json(a.benchmark_report),cfg['_jobs'],cfg['max_credit_multiplier'])
    if not result:
        p.error('Specify --task-id and/or --benchmark-report')
    print(json.dumps(result,indent=2))
    return 0 if all(all(x.values()) for x in result.values()) else 1

if __name__=='__main__':
    raise SystemExit(main())
