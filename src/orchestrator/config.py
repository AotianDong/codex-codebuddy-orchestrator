import json
import os
from decimal import Decimal
from pathlib import Path

def default_state():
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'codex-codebuddy'
    return Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'codex-codebuddy'

def load(path=None):
    path = Path(path or os.environ.get('CBO_CONFIG') or default_state() / 'config.yaml').expanduser().resolve()
    value = json.loads(path.read_text('utf-8-sig'))
    defaults = {'codebuddy_cli': '', 'node_path': '', 'candidate_models': [],
                'max_credit_multiplier': '0.2', 'default_model': None,
                'benchmark_enabled': True, 'agent_timeout_seconds': 180,
                'max_reworks': 1, 'test_commands': [], 'log_directory': 'jobs'}
    if not isinstance(value, dict) or value.keys() - defaults.keys():
        raise ValueError('Unknown configuration keys')
    defaults.update(value)
    value = defaults
    rate = Decimal(str(value['max_credit_multiplier']))
    if not rate.is_finite() or rate <= 0:
        raise ValueError('max_credit_multiplier must be finite and positive')
    if type(value['max_reworks']) is not int or value['max_reworks'] not in (0, 1):
        raise ValueError('max_reworks must be 0 or 1')
    if type(value['agent_timeout_seconds']) is not int or not 1 <= value['agent_timeout_seconds'] <= 600:
        raise ValueError('agent_timeout_seconds must be 1..600')
    if not isinstance(value['candidate_models'], list) or not value['candidate_models'] or any(
            not isinstance(m, str) or not m for m in value['candidate_models']):
        raise ValueError('candidate_models must be a non-empty string list')
    if value['default_model'] is not None and value['default_model'] not in value['candidate_models']:
        raise ValueError('default_model must be a candidate')
    state = path.parent
    log = Path(value['log_directory']).expanduser()
    value.update(_path=path, _state=state, _jobs=log.resolve() if log.is_absolute() else (state / log).resolve())
    return value
