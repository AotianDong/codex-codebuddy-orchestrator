"""Small, path-free real-task records; benchmark scores remain a separate source."""
from collections import defaultdict
from pathlib import Path
from .scheduler import now, write_json, read_json

def record_result(report, directory, origin='real_task'):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    calls = report.get('model_calls', [])
    models = sorted({x['model_id'] for x in calls})
    value = {'task_id': report['task_id'], 'origin': origin, 'at': now(), 'models': models,
             'success': report.get('state') == 'succeeded' and report.get('source_unchanged') is True
                        and bool(report.get('acceptance'))
                        and all(x.get('verdict') == 'passed' for x in report['acceptance']),
             'state': report['state'], 'reworks': max(0, len(report.get('attempts', [])) - 1),
             'failure_kind': report.get('failure_kind'), 'actual_credits': None,
             'seconds': sum(x.get('duration_seconds', 0) for x in calls),
             'test_passed': sum(t.get('exit_code') == 0 for a in report.get('attempts', [])[-1:] for t in a['tests']),
             'test_total': sum(len(a['tests']) for a in report.get('attempts', [])[-1:])}
    write_json(directory / (report['task_id'] + '.json'), value)
    return value

def summarize_history(directory):
    groups = defaultdict(list)
    for p in Path(directory).glob('*.json'):
        row = read_json(p)
        # Mixed-model attempts do not create a model-specific success observation.
        if row['origin'] == 'real_task' and len(row['models']) == 1:
            groups[row['models'][0]].append(row)
    return {'origin': 'real_task', 'routing_effect': 'observational only; paired benchmark controls routing',
            'models': {m: {'samples': len(rows), 'success_rate': sum(x['success'] for x in rows) / len(rows),
                           'test_pass_rate': sum(x['test_passed'] for x in rows) / max(1, sum(x['test_total'] for x in rows)),
                           'rework_rate': sum(x['reworks'] > 0 for x in rows) / len(rows),
                           'average_inference_seconds': sum(x['seconds'] for x in rows) / len(rows),
                           'actual_credits': None,
                           'uncertainty': 'small/uncontrolled samples; no automatic winner claim'}
                       for m, rows in groups.items()}}
