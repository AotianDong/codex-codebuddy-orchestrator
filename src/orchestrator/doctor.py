import platform
import shutil
import sys
from .runtime import discover_cli, cli_command, cli_version
from .model_policy import ModelPolicy

def inspect(cfg):
    node, cli = discover_cli()
    node, cli = cfg['node_path'] or node, cfg['codebuddy_cli'] or cli
    result = {'python': platform.python_version(), 'platform': platform.system(),
              'git_found': bool(shutil.which('git')), 'codex_cli_found': bool(shutil.which('codex')),
              'integration': 'local Skill requires shell access; Work/managed environments need their supported local executor',
              'codebuddy_found': False, 'model_eligible': [], 'ready_for_execution': False}
    try:
        cli_command(node, cli)
        result.update(codebuddy_found=True, codebuddy_version=cli_version(cli, node))
        ok, rejected = ModelPolicy(cfg['_state'] / 'models.json', cli).eligible()
        result.update(model_eligible=list(ok), model_rejected=rejected)
    except Exception as exc:
        result['next_action'] = str(exc) + '; run models-refresh then models-probe after CodeBuddy authentication'
    result['ready_for_execution'] = sys.version_info >= (3, 10) and result['git_found'] and result['codebuddy_found'] and bool(result['model_eligible'])
    return result
