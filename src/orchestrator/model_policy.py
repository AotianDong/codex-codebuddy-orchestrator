"""Fail-closed model policy, separate from project tasks and Agent output."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from .runtime import cli_version
import re

HARD_MAX = Decimal('0.2')
APPROVED = {'deepseek-v4.1-flash', 'minimax-m3.1-flash'}
WEIGHTS = {'tests': 35, 'first_pass': 20, 'quality': 15, 'rework': 10, 'speed': 10, 'cost': 10}


class PolicyError(Exception):
    def __init__(self, kind, detail):
        self.kind, self.detail = kind, detail
        super().__init__(detail)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def instant(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00')).astimezone(timezone.utc)


class ModelPolicy:
    def __init__(self, path, cli):
        self.path, self.cli = Path(path).resolve(), Path(cli).resolve()

    def data(self):
        try:
            value = load(self.path)
            maximum = Decimal(str(value['max_credit_multiplier']))
            if not maximum.is_finite() or not 0 < maximum:
                raise PolicyError('credit_limit_exceeded', 'Configured threshold must be finite and positive')
            return value
        except (OSError, KeyError, ValueError, InvalidOperation) as exc:
            raise PolicyError('policy_invalid', str(exc)) from exc

    def verified(self, model_id, headless=True):
        data = self.data()
        if model_id not in APPROVED or model_id not in data.get('models', {}):
            raise PolicyError('model_not_whitelisted', model_id)
        model = data['models'][model_id]
        if model.get('credit_multiplier') is None:
            raise PolicyError('credit_multiplier_unknown', model_id)
        try:
            multiplier = Decimal(str(model['credit_multiplier']))
            maximum = Decimal(str(data['max_credit_multiplier']))
            if not multiplier.is_finite() or multiplier < 0:
                raise InvalidOperation
        except InvalidOperation as exc:
            raise PolicyError('credit_multiplier_unknown', model_id) from exc
        if multiplier >= maximum:
            raise PolicyError('credit_limit_exceeded', f'{model_id}: {multiplier} >= {maximum}')
        try:
            evidence_path = (self.path.parent / model['rate_evidence']).resolve()
            evidence = load(evidence_path)
            if sha(evidence_path) != model['rate_evidence_sha256']:
                raise PolicyError('rate_evidence_invalid', 'Catalog changed; explicitly reverify')
            age = datetime.now(timezone.utc) - instant(evidence['verified_at'])
            lifetime = min(int(data.get('evidence_valid_hours', 24)), 24)
            if age < timedelta(minutes=-5) or age > timedelta(hours=lifetime):
                raise PolicyError('rate_evidence_stale', model_id)
            package = self.cli.parent.parent / 'package.json'
            if evidence['cli_version'] != cli_version(str(self.cli)):
                raise PolicyError('rate_evidence_stale', 'CLI version changed; reverify catalog and availability')
            values = evidence['models'][model_id]
            rates = [v.get('_meta', {}).get('credits', v.get('description', '')) for v in values]
            verified_rates = [Decimal(re.fullmatch(r'x(\d+(?:\.\d+)?)\s*(?:credits)?', r).group(1))
                              for r in rates if re.fullmatch(r'x(\d+(?:\.\d+)?)\s*(?:credits)?', r)]
            if not verified_rates or any(r != multiplier for r in verified_rates):
                raise PolicyError('rate_evidence_invalid', 'Configured rate differs from account-visible catalog')
            if evidence.get('source_kind') != 'cli_acp_account_catalog':
                raise PolicyError('rate_evidence_invalid', 'Require official CLI account catalog evidence')
        except PolicyError:
            raise
        except (OSError, ValueError, KeyError, TypeError, InvalidOperation) as exc:
            raise PolicyError('rate_evidence_invalid', str(exc)) from exc
        if not model.get('available_verified') or (headless and not model.get('headless_verified')):
            raise PolicyError('model_unavailable', model_id + ': live headless verification required')
        if headless:
            try:
                probe = load(self.path.parent / model['availability_evidence'])
                if (probe.get('state') != 'succeeded' or probe.get('model_id') != model_id
                        or not probe.get('agent_session_id')
                        or probe.get('selection', {}).get('rate_verified_at') != evidence['verified_at']
                        or probe.get('consumption', {}).get('observed_model_ids') != [model_id]):
                    raise ValueError('Probe identity, result or catalog generation mismatch')
            except (OSError, KeyError, TypeError, ValueError) as exc:
                raise PolicyError('model_unavailable', 'Verified Headless evidence missing or invalid') from exc
        return {'model_id': model_id, 'credit_multiplier': str(multiplier),
                'rate_verified_at': evidence['verified_at'], 'rate_evidence': str(evidence_path),
                'policy_sha256': sha(self.path)}

    def eligible(self, headless=True):
        ok, rejected = {}, {}
        for mid in self.data().get('models', {}):
            try:
                ok[mid] = self.verified(mid, headless)
            except PolicyError as exc:
                rejected[mid] = {'kind': exc.kind, 'detail': exc.detail}
        return ok, rejected

    def choose(self, manual=None, excluded=(), headless=True):
        if manual:
            selected = self.verified(manual, headless)
            if manual in excluded:
                raise PolicyError('model_unavailable', 'Pinned model unavailable; manual pin never silently changes')
            selected['reason'] = 'manual whitelist pin; strict credit check passed'
            return selected
        candidates, rejected = self.eligible(headless)
        candidates = {k: v for k, v in candidates.items() if k not in excluded}
        if not candidates:
            raise PolicyError('no_compliant_model', json.dumps(rejected, ensure_ascii=False))
        data = self.data()
        report_file = self.path.parent / data.get('benchmark_report', 'benchmark/latest.json')
        if report_file.is_file():
            report = load(report_file)
            recommendation = report.get('recommendation')
            current = (report.get('scheduler_sha256') == sha(Path(__file__).with_name('scheduler.py'))
                     and report.get('policy_rate_signature') == self.rate_signature()
                     and datetime.now(timezone.utc) - instant(report['finished_at']) < timedelta(days=7))
            if current:
                # A cheap candidate with objective poor correctness is not a bootstrap fallback.
                for mid, result in report.get('models', {}).items():
                    if result.get('distinct_tasks', 0) >= 10 and (
                            result.get('final_success_rate', 0) < .9 or result.get('quality_rate', 0) < .9):
                        candidates.pop(mid, None)
                if not candidates:
                    raise PolicyError('no_compliant_model', 'Current benchmark rejects all candidates on correctness/quality')
            if current and report.get('valid_for_routing') is True and recommendation in candidates:
                selected = candidates[recommendation]
                selected['reason'] = 'latest valid benchmark: ' + report.get('recommendation_reason', '')
                return selected
        # Not a performance winner: explicit conservative bootstrap selection.
        mid = data.get('default_model')
        if mid not in candidates:
            mid = min(candidates, key=lambda m: (Decimal(candidates[m]['credit_multiplier']), m))
        selected = candidates[mid]
        selected['reason'] = 'explicit default or cheapest verified cold-start candidate; no decisive benchmark winner'
        return selected

    def rate_signature(self):
        data = self.data()
        fields = {m: {'rate': x.get('credit_multiplier'), 'evidence': x.get('rate_evidence_sha256')}
                  for m, x in data['models'].items()}
        return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def classify_cli(out, err, rc):
    text = (out + '\n' + err).lower()
    if re.search(r'permission denied|permission_denied|\beacces\b|\beperm\b', text):
        return 'permission_denied'
    if re.search(r'model.*(not found|unavailable|not available|service info|not supported)|\b(429|503)\b|rate.limit|overloaded', text):
        return 'model_unavailable'
    return 'cli_failed' if rc != 0 else None


def telemetry(text, requested):
    try:
        events = json.loads(text)
        if isinstance(events, dict):
            events = [events]
        final = next(x for x in reversed(events) if x.get('type') == 'result')
    except (ValueError, TypeError, StopIteration):
        return {'credits': None, 'credits_kind': 'unavailable', 'usage': None, 'requested_model_id': requested}
    observed = set()
    def walk(value):
        if isinstance(value, dict):
            for key, val in value.items():
                if key in ('model', 'modelId', 'model_id') and isinstance(val, str):
                    observed.add(val)
                elif isinstance(val, (dict, list)):
                    walk(val)
        elif isinstance(value, list):
            for val in value:
                walk(val)
    walk(events)
    return {'requested_model_id': requested, 'observed_model_ids': sorted(observed),
            'usage': final.get('usage'), 'cli_reported_cost_usd': final.get('total_cost_usd'),
            'credits': None, 'credits_kind': 'unavailable',
            'cost_note': 'CLI USD field is not account credits; zero does not prove free usage',
            'num_turns': final.get('num_turns'), 'agent_session_id': final.get('session_id')}
