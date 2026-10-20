"""Sequential paired benchmark using the existing Scheduler, no extra Agent tools."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import statistics
import time
from .model_policy import ModelPolicy, PolicyError, WEIGHTS, sha
from . import scheduler as s

BASE = Path(__file__).resolve().parent
BENCH = Path.home() / '.local/state/codex-codebuddy/benchmark'


def mean(values):
    return statistics.mean(values) if values else 0.0


def metrics(report, elapsed):
    attempts = report.get('attempts', [])
    tests = attempts[-1].get('tests', []) if attempts else []
    checks = [x for x in tests if x['id'] != 'quality']
    passed = sum(x.get('exit_code') == 0 for x in checks)
    success = report.get('state') == 'succeeded' and report.get('source_unchanged') is True
    first = success and len(attempts) == 1
    raw_tokens, proxy = 0, 0.0
    has_usage = bool(report.get('model_calls'))
    for call in report.get('model_calls', []):
        usage = call.get('consumption', {}).get('usage')
        if not usage:
            has_usage = False
            continue
        # input_tokens already contains cache tokens in this CLI; do not double count.
        tokens = (usage.get('input_tokens') or 0) + (usage.get('output_tokens') or 0)
        raw_tokens += tokens
        proxy += tokens * float(call['credit_multiplier'])
    return {'success': success, 'first_pass': first, 'test_passed': passed,
            'test_total': len(checks), 'test_fraction': passed / len(checks) if checks else 0,
            'quality': float(success and any(x['id'] == 'quality' and x.get('exit_code') == 0 for x in tests)),
            'reworks': max(0, len(attempts) - 1), 'seconds': elapsed,
            'timeout': report.get('failure_kind') in ('timeout', 'model_timeout'),
            'token_total': raw_tokens if has_usage else None,
            'relative_cost_proxy': proxy if has_usage else None,
            'actual_credits': None, 'actual_credits_status': 'not_exposed_by_CLI',
            'failure_kind': report.get('failure_kind')}


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['model_id']].append(row)
    summaries = {}
    for mid, samples in groups.items():
        items = [x['metrics'] for x in samples]
        first_failed = [x for x in items if not x['first_pass']]
        repaired = sum(x['success'] and x['reworks'] > 0 for x in first_failed)
        credit_proxies = [x['relative_cost_proxy'] for x in items]
        summary = {'runs': len(items), 'distinct_tasks': len({x['case_id'] for x in samples}),
                   'final_success_rate': mean([float(x['success']) for x in items]),
                   'first_pass_rate': mean([float(x['first_pass']) for x in items]),
                   'test_pass_rate': sum(x['test_passed'] for x in items) / sum(x.get('test_total', 3) for x in items) if sum(x.get('test_total', 3) for x in items) else 0,
                   'quality_rate': mean([x['quality'] for x in items]),
                   'rework_success_rate': repaired / len(first_failed) if first_failed else None,
                   'average_reworks': mean([x['reworks'] for x in items]),
                   'average_seconds': mean([x['seconds'] for x in items]),
                   'timeout_rate': mean([float(x['timeout']) for x in items]),
                   'relative_cost_proxy_mean': mean(credit_proxies) if all(x is not None for x in credit_proxies) else None,
                   'actual_credits': None, 'token_total': sum(x['token_total'] or 0 for x in items),
                   'tool_calls': 0, 'by_category': {}}
        for category in sorted({x['category'] for x in samples}):
            part = [x['metrics'] for x in samples if x['category'] == category]
            summary['by_category'][category] = {'runs': len(part), 'success_rate': mean([float(x['success']) for x in part]),
                                               'average_seconds': mean([x['seconds'] for x in part])}
        # Equal task weighting prevents repeated core cases dominating the score.
        task_scores = {}
        for cid in sorted({x['case_id'] for x in samples}):
            part = [x['metrics'] for x in samples if x['case_id'] == cid]
            failed = [x for x in part if not x['first_pass']]
            rework_component = (sum(x['success'] and x['reworks'] > 0 for x in failed) / len(failed)) if failed else 1.0
            task_scores[cid] = {
                'tests': mean([x['test_fraction'] for x in part]),
                'first_pass': mean([float(x['first_pass']) for x in part]),
                'quality': mean([x['quality'] for x in part]), 'rework': rework_component,
                'speed': mean([max(0.0, 1 - x['seconds'] / 300.0) for x in part])}
        summary['proxy_cost_per_successful_task'] = (
            sum(credit_proxies) / sum(x['success'] for x in items)
            if all(x is not None for x in credit_proxies) and any(x['success'] for x in items) else None)
        summary['actual_credit_cost_per_successful_task'] = None
        summary['task_components'] = task_scores
        summaries[mid] = summary
    proxies = [x['relative_cost_proxy_mean'] for x in summaries.values() if x['relative_cost_proxy_mean'] is not None]
    minimum = min(proxies) if proxies else None
    for summary in summaries.values():
        own = summary['relative_cost_proxy_mean']
        cost_score = min(1.0, minimum / own) if minimum is not None and own and own > 0 else None
        components = {k: mean([x[k] for x in summary['task_components'].values()]) for k in WEIGHTS if k != 'cost'}
        components['cost'] = cost_score
        summary['score_components'] = components
        summary['weighted_components'] = {k: v * WEIGHTS[k] if v is not None else None for k, v in components.items()}
        summary['score'] = sum(v for v in summary['weighted_components'].values() if v is not None) if cost_score is not None else None
        summary['score_without_cost_out_of_90'] = sum(v for k, v in summary['weighted_components'].items() if k != 'cost')
        summary['score_kind'] = 'estimated_cost_proxy_included' if cost_score is not None else 'incomplete_cost_unknown'
    return summaries


def recommendation(summaries, rows):
    safe = {m: x for m, x in summaries.items() if x['distinct_tasks'] >= 10 and x['final_success_rate'] >= .9
            and x['quality_rate'] >= .9 and x['score'] is not None}
    if len(safe) < 2:
        return None, 'Insufficient paired eligible samples or correctness/quality gate not met', None
    ordered = sorted(safe, key=lambda m: (-safe[m]['score'], -safe[m]['test_pass_rate'], -safe[m]['first_pass_rate']))
    a, b = ordered[:2]
    gap = safe[a]['score'] - safe[b]['score']
    # Task-level paired bootstrap of deterministic non-cost quality points.
    common = sorted(set(safe[a]['task_components']) & set(safe[b]['task_components']))
    diffs = [sum((safe[a]['task_components'][c][k] - safe[b]['task_components'][c][k]) * WEIGHTS[k]
                 for k in WEIGHTS if k != 'cost') for c in common]
    rng = random.Random(20261020)
    boot = sorted(mean(rng.choices(diffs, k=len(diffs))) for _ in range(2000))
    interval = [boot[50], boot[1949]]
    # Strictly avoid declaring a winner based only on an unknown actual cost estimate.
    if gap < 3 or interval[0] <= 0:
        return None, 'No clear winner: score gap <3 or paired non-cost evidence does not favor the estimated-cost score leader', interval
    # Core cases must each have >=3 independent samples for both models.
    counts = defaultdict(int)
    for row in rows:
        counts[row['model_id'], row['case_id']] += 1
    if any(counts[m, cid] < 3 for m in (a, b) for cid in ('C1', 'E1')):
        return None, 'Core repeats <3; performance recommendation remains provisional', interval
    return a, 'Paired quality evidence and estimated-cost score favor this model; credits remain unknown', interval


def render(report, job_prefix='../jobs/'):
    lines = ['# CodeBuddy V2 模型基准测评', '', '此报告由真实执行记录计算，成本维度包含明确标注的相对代理量。', '',
             f"完成时间（UTC）：{report['finished_at']}；CLI {report['cli_version']}", '',
             '| 模型 | 倍率 | 样本 | 一次成功 | 最终任务成功 | 测试通过 | 平均秒数 | 综合分 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for mid, x in report['models'].items():
        score = f"{x['score']:.2f}" if x['score'] is not None else '缺失'
        lines.append(f"| {mid} | {report['rates'][mid]} | {x['runs']} | {x['first_pass_rate']:.1%} | {x['final_success_rate']:.1%} | {x['test_pass_rate']:.1%} | {x['average_seconds']:.2f} | {score} |")
    lines += ['', '推荐：' + (report['recommendation'] or '**暂未确定明显优胜者**'),
              '', report['recommendation_reason'], '', '## 各任务记录', '',
              '| 任务 | 类别 | 模型 | 重复 | 状态 | 测试 | 返工 | 秒数 | 日志 |', '|---|---|---|---:|---|---:|---:|---:|---|']
    for row in report['runs']:
        x = row['metrics']
        link = job_prefix + row['task_id'] + '/report.json'
        lines.append(f"| {row['case_id']} | {row['category']} | {row['model_id']} | {row['repeat']} | {row['state']} | {x['test_passed']}/{x['test_total']} | {x['reworks']} | {x['seconds']:.2f} | [记录]({link}) |")
    lines += ['', '## 评分与局限', '',
              '权重：测试35、一次成功20、自动质量15、返工10、速度10、成本10。每个任务等权，核心任务重复不增加其权重。',
              '测试=最终3条功能检查通过比例；质量=固定AST安全/规模检查通过且任务成功；返工=首次失败后的成功比例，无失败时中性满分（不能证明返工能力）；速度=max(0,1-总耗时/300)。',
              '成本分使用 min(候选平均代理量)/本模型平均代理量；代理量=倍率×(CLI input_tokens+output_tokens)，未另加已包含的缓存输入。没有官方积分换算，不区分输入/输出/缓存单价，不能称为真实积分。',
              'CLI total_cost_usd=0 也不能证明免费。JSON 保留原始 Token 与 CLI 费用字段，实际积分为 null。',
              '任务较小，只代表本地空工具提议工作流。未测自主工具使用、生产仓库、大型仓库、联网工具和长期 Agent。',
              '统一 effort=high、max-turns=1、最多一次返工、120秒模型时限；未设置温度/随机种子（当前CLI无统一参数）。执行顺序交替，仍可能受网络/缓存影响。',
              '模型选择要求至少10个相同任务、C1/E1各3次、正确性和质量>=90%；差距不足3分，或任务级非成本差值bootstrap区间不能支持领先者，则不强行推荐。不凭未知真实积分的代理量逆转非成本证据。',
              '代码质量分是有限的确定性代理检查，不等于全面可维护性或安全评审。', '']
    return '\n'.join(lines)


def build_report(run_dir, policy):
    rows = s.read_json(run_dir / 'progress.json')['runs']
    for cid in {x['case_id'] for x in rows}:
        pair = [x for x in rows if x['case_id'] == cid]
        if len({x['model_id'] for x in pair}) != 2 or len({x['source_head'] for x in pair}) != 1 or len({x['task_manifest_sha256'] for x in pair}) != 1:
            raise PolicyError('unpaired_conditions', 'Models must share baseline and manifest for every case')
    summaries = summarize(rows)
    choice, reason, interval = recommendation(summaries, rows)
    evidence = s.read_json(policy.path.parent / 'catalog/catalog.json')
    report = {'version': 2, 'origin': 'benchmark', 'finished_at': s.now(), 'cli_version': evidence['cli_version'],
              'scheduler_sha256': sha(Path(__file__).with_name('scheduler.py')), 'benchmark_sha256': sha(Path(__file__)),
              'policy_rate_signature': policy.rate_signature(), 'weights': WEIGHTS,
              'rates': {m: policy.verified(m)['credit_multiplier'] for m in summaries},
              'models': summaries, 'runs': rows, 'recommendation': choice,
              'recommendation_reason': reason, 'paired_non_cost_interval_95': interval,
              'valid_for_routing': choice is not None,
              'actual_credits': None, 'cost_is_proxy': True}
    s.write_json(run_dir / 'report.json', report)
    (run_dir / 'report.md').write_text(render(report, '../../jobs/'), encoding='utf-8')
    s.write_json(BENCH / 'latest.json', report)
    (BENCH / 'latest.md').write_text(render(report), encoding='utf-8')
    data = policy.data()
    for mid, entry in data['models'].items():
        entry.update(benchmark_entered=mid in summaries, benchmark_score=summaries.get(mid, {}).get('score'),
                     default_preferred=mid == choice)
    s.write_json(policy.path, data)
    return report


def run_suite(models_file, core_repeats=True, *, node=None, cli=None, jobs=None, bench_dir=None):
    global BENCH
    BENCH = Path(bench_dir) if bench_dir else BENCH
    policy = ModelPolicy(models_file, cli or s.DEFAULT_CLI)
    eligible, rejected = policy.eligible()
    # Never silently perform an unpaired comparison when a requested model is blocked.
    if set(eligible) != {'deepseek-v4.1-flash', 'minimax-m3.1-flash'}:
        raise PolicyError('no_compliant_model', json.dumps(rejected))
    index = s.read_json(BENCH / 'suite/index.json')
    run_dir = BENCH / ('run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
    run_dir.mkdir()
    rows = []
    s.write_json(run_dir / 'conditions.json', {'suite_index_sha256': sha(BENCH / 'suite/index.json'),
                 'models': list(eligible), 'effort': 'high', 'max_reworks': 1, 'agent_timeout': 120,
                 'seed': None, 'temperature': None, 'core_repeats': core_repeats,
                 'environment': __import__('platform').platform(), 'python': __import__('sys').version})
    ordered = sorted(eligible)
    for position, case in enumerate(index['tasks']):
        repeats = case['core_repeats'] if core_repeats else 1
        for repeat in range(1, repeats + 1):
            for mid in ordered if (position + repeat) % 2 else list(reversed(ordered)):
                # Recheck every inference; any now-ineligible model halts the comparison.
                policy.verified(mid)
                service = s.Scheduler(jobs=jobs or s.DEFAULT_JOBS, node=node or s.DEFAULT_NODE, cli=cli or s.DEFAULT_CLI, models=models_file, model=mid)
                manifest = BENCH / 'suite' / case['manifest']
                task_id = service.submit(manifest)
                started = time.monotonic()
                report = service.run(task_id)
                row = {'case_id': case['id'], 'category': case['category'], 'repeat': repeat,
                       'model_id': mid, 'task_id': task_id, 'state': report['state'],
                       'task_manifest_sha256': sha(manifest), 'source_head': report.get('source_head'),
                       'difficulty': case.get('difficulty', 'small'), 'at': s.now(),
                       'metrics': metrics(report, time.monotonic() - started)}
                rows.append(row)
                s.write_json(run_dir / 'progress.json', {'runs': rows})
                print(json.dumps(row, ensure_ascii=False), flush=True)
                if report.get('failure_kind') in ('credit_limit_exceeded','credit_multiplier_unknown','rate_evidence_stale',
                                                  'rate_evidence_invalid','model_not_whitelisted','source_changed'):
                    raise PolicyError(report['failure_kind'], 'Benchmark halted; preserve partial records')
    final = build_report(run_dir, policy)
    print(json.dumps({'report': str(run_dir / 'report.md'), 'recommendation': final['recommendation']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', type=Path, default=BASE / 'models.json')
    parser.add_argument('--single-repeat', action='store_true')
    parser.add_argument('--report-only', type=Path)
    args = parser.parse_args()
    if args.report_only:
        build_report(args.report_only, ModelPolicy(args.models, s.DEFAULT_CLI))
    else:
        run_suite(args.models.resolve(), not args.single_repeat)
