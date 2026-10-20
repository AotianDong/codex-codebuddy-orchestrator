"""Configure from verified account catalog; probe only below-ceiling candidates."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
from .model_policy import APPROVED, ModelPolicy, PolicyError, sha, telemetry
from . import scheduler as s
from .runtime import cli_command

BASE = Path(__file__).resolve().parent


def configure(catalog, policy_file, maximum="0.2", default_model=None):
    base = policy_file.parent
    evidence = s.read_json(catalog)
    if evidence.get('source_kind') != 'cli_acp_account_catalog':
        raise ValueError('Require current CLI account catalog')
    models = {}
    for mid in sorted(APPROVED):
        values = evidence.get('models', {}).get(mid, [])
        rate = None
        for value in values:
            match = re.fullmatch(r'x(\d+(?:\.\d+)?)\s*(?:credits)?',
                                 value.get('_meta', {}).get('credits', value.get('description', '')))
            if match:
                current = match.group(1)
                if rate is not None and Decimal(rate) != Decimal(current):
                    raise ValueError('Conflicting rates')
                rate = current
        models[mid] = {'name': values[0].get('name', mid) if values else mid, 'model_id': mid, 'credit_multiplier': rate,
                       'rate_source': 'official CLI ACP account catalog',
                       'rate_evidence': str(catalog.relative_to(base)), 'rate_evidence_sha256': sha(catalog),
                       'verified_at': evidence['verified_at'], 'available_verified': bool(values),
                       'headless_verified': False, 'compliant': rate is not None and Decimal(rate) < Decimal(str(maximum)),
                       'benchmark_entered': False, 'benchmark_score': None, 'default_preferred': False}
    s.write_json(policy_file, {'version': 2, 'max_credit_multiplier': str(maximum), 'default_model': default_model, 'evidence_valid_hours': 24,
                              'benchmark_report': 'benchmark/latest.json', 'models': models})


def probe(policy_file, node=None, cli=None):
    service = s.Scheduler(models=policy_file, node=node or s.DEFAULT_NODE, cli=cli or s.DEFAULT_CLI)
    data = s.read_json(policy_file)
    for mid in data['models']:
        target = policy_file.parent / 'probes' / mid
        target.mkdir(parents=True, exist_ok=True)
        session = 'probe-' + s.uuid.uuid4().hex
        result = {'model_id': mid, 'at': s.now(), 'session_id_requested': session, 'state': 'failed'}
        try:
            selection = service.policy.verified(mid, headless=False)
            result['selection'] = selection
            argv = cli_command(service.node, service.cli) + ['--print', '--output-format', 'json', '--tools', '',
                    '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--setting-sources', '',
                    '--no-session-persistence', '--session-id', session, '--max-turns', '1',
                    '--model', mid, '--fallback-model', mid, '--effort', 'high']
            meta, out, err = service.command(target, 'probe-' + mid, argv, target, 90,
                                             'Return ONLY JSON {"changes":[]}. No tools.', agent=True)
            if meta['exit_code']:
                raise s.Failure('cli_failed', 'Probe nonzero exit code')
            sid, proposal = s.parse_agent(out)
            if proposal != {'changes': []}:
                raise s.Failure('json_parse_failed', 'Unexpected probe response')
            consumption = telemetry(out, mid)
            if consumption.get('observed_model_ids') != [mid]:
                raise s.Failure('model_identity_mismatch', 'Unexpected observed model')
            result.update(state='succeeded', agent_session_id=sid, consumption=consumption,
                          duration_seconds=meta['duration_seconds'])
            data['models'][mid].update(headless_verified=True, headless_verified_at=s.now(),
                                      availability_evidence=str((target / 'result.json').relative_to(policy_file.parent)))
        except (PolicyError, s.Failure) as exc:
            result.update(failure_kind=exc.kind, detail=exc.detail)
            data['models'][mid]['headless_verified'] = False
        s.write_json(target / 'result.json', result)
        s.write_json(policy_file, data)
        print(json.dumps(result, ensure_ascii=False), flush=True)
