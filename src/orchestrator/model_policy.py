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
PRIMARY = 'deepseek-v4.1-flash'
FALLBACK = 'minimax-m3.1-flash'
SERVICE_FAILURES = {'model_unavailable', 'model_rate_limited', 'model_service_error'}
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
            if not maximum.is_finite() or not 0 < maximum <= HARD_MAX:
                raise PolicyError('credit_limit_exceeded', 'Configured threshold must be positive and <=0.2')
            if value.get('primary_model', PRIMARY) != PRIMARY:
                raise PolicyError('policy_invalid', 'Only the fixed DeepSeek primary is permitted')
            if value.get('fallback_model') not in (None, FALLBACK):
                raise PolicyError('model_not_whitelisted', 'Only the exact MiniMax fallback is permitted')
            retries = value.get('max_technical_retries', 1)
            if type(retries) is not int or not 0 <= retries <= 2:
                raise PolicyError('policy_invalid', 'max_technical_retries must be 0..2')
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
        data = self.data()
        if PRIMARY not in excluded:
            selected = self.verified(PRIMARY, headless)
            selected['reason'] = 'fixed primary priority; benchmark and price ranking do not override'
            return selected
        if (data.get('fallback_model') != FALLBACK or data.get('fallback_model_verified') is not True
                or FALLBACK in excluded):
            raise PolicyError('fallback_unavailable', 'Primary failed; no qualified configured MiniMax fallback')
        selected = self.verified(FALLBACK, headless)
        selected['reason'] = 'qualified MiniMax fallback after an explicit primary service failure'
        return selected

    def rate_signature(self):
        data = self.data()
        fields = {m: {'rate': x.get('credit_multiplier'), 'evidence': x.get('rate_evidence_sha256')}
                  for m, x in data['models'].items()}
        return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def classify_cli(out, err, rc):
    # Only error messages may authorize switching; never scan generated code/prose.
    messages = [err]
    final_success = False
    if out:
        try:
            events = json.loads(out)
            if isinstance(events, dict):
                events = [events]
            final_success = any(isinstance(e, dict) and e.get('type') == 'result'
                                and e.get('is_error') is False for e in events)
            messages.extend(str(e.get('result', '')) for e in events
                            if isinstance(e, dict) and e.get('type') == 'result' and e.get('is_error') is True)
        except (ValueError, TypeError):
            pass
    text = '\n'.join(messages).lower()
    if re.search(r'permission denied|permission_denied|\beacces\b|\beperm\b', text):
        return 'permission_denied'
    if rc == 0 and final_success:
        return None  # Historical service warnings cannot turn a valid result into a failover.
    if re.search(r'(?:http|status(?: code)?)[ :="\x27]*(?:408|504)\b|(?:model|inference|upstream|gateway|api request).{0,60}(?:timed?\s*out|timeout)', text):
        return 'model_timeout'
    if re.search(r'(?:http|status(?: code)?)[ :="\x27]*429\b|rate[ _-]?limit(?:[ _-]error| exceeded| reached)|too many requests|model.{0,40}(?:capacity|overloaded)', text):
        return 'model_rate_limited'
    if re.search(r'(?:http|status(?: code)?)[ :="\x27]*(?:500|502|503|529)\b|model service.{0,40}(?:error|failure)', text):
        return 'model_service_error'
    if re.search(r'model.{0,60}(?:not found|unavailable|not available|service info|not supported)', text):
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
