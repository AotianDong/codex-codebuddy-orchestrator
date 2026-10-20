"""Install/update an owned, self-contained Skill. No global pip or config changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import venv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from orchestrator.config import default_state
from orchestrator.runtime import discover_cli, cli_command

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def default_skills():
    # Prefer an existing Codex custom home; current official user discovery otherwise.
    if os.environ.get('CODEX_HOME'):
        return Path(os.environ['CODEX_HOME']).expanduser() / 'skills'
    return Path.home() / '.agents/skills'

def safe_tree(path):
    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
        raise ValueError('Linked installation paths are unsupported')
    for p in path.rglob('*'):
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('Linked installation content is unsupported')

def verify_owned(dest):
    safe_tree(dest)
    m = json.loads((dest / '.installation.json').read_text('utf-8'))
    if m.get('project') != 'codex-codebuddy-orchestrator' or m.get('path') != str(dest.resolve()):
        raise ValueError('Unowned or relocated Skill; refusing overwrite/delete')
    actual = {p.relative_to(dest).as_posix(): sha(p) for p in dest.rglob('*')
              if p.is_file() and p != dest / '.installation.json'}
    if actual != m['files']:
        raise ValueError('Installed files changed or unknown files present; back up changes before update/uninstall')
    return m

def install(dest, state, update=False):
    if sys.version_info < (3, 10):
        raise ValueError('Python >=3.10 required')
    if not shutil.which('git'):
        raise ValueError('Git required')
    node, cli = discover_cli()
    cli_command(node, cli)
    if dest.exists():
        if not update:
            raise ValueError('Skill already exists; use update for owned installations')
        verify_owned(dest)
    # Reject linked parents too; do not redirect mutations through an existing link.
    for parent in [dest.parent, *dest.parent.parents]:
        if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
            raise ValueError('Linked parent path is unsupported')
    dest.parent.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    cfg = state / 'config.yaml'
    if not cfg.exists():
        with cfg.open('x', encoding='utf-8') as f:
            f.write((ROOT / 'config.example.yaml').read_text('utf-8'))
    temporary = Path(tempfile.mkdtemp(prefix='.cbo-install-', dir=dest.parent))
    backup = None
    published = False
    try:
        shutil.copytree(ROOT / 'skills/codex-codebuddy', temporary, dirs_exist_ok=True)
        shutil.copytree(ROOT / 'src/orchestrator', temporary / 'scripts/runtime/orchestrator',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        venv.create(temporary / '.venv', with_pip=False, symlinks=False)
        metadata = {'project': 'codex-codebuddy-orchestrator', 'version': '0.1.0',
                    'path': str(dest.resolve()), 'config': str(cfg.resolve())}
        (temporary / 'scripts/local.json').write_text(json.dumps({'config': metadata['config']}), encoding='utf-8')
        metadata['files'] = {p.relative_to(temporary).as_posix(): sha(p)
                             for p in temporary.rglob('*') if p.is_file()}
        (temporary / '.installation.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        if dest.exists():
            backup = dest.with_name('.cbo-backup-' + uuid.uuid4().hex)
            dest.rename(backup)
        temporary.rename(dest)
        published = True
        # venv launchers are not used; direct interpreter remains relocatable on tested Windows.
        py = dest / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        subprocess.run([str(py), '-B', str(dest / 'scripts/run.py'), '--help'], check=True, capture_output=True)
        check = subprocess.run([str(py), '-B', str(dest / 'scripts/run.py'), 'doctor'],
                               capture_output=True, text=True, encoding='utf-8')
        if check.returncode not in (0, 2):
            raise ValueError('Installed dispatcher doctor failed')
        health = json.loads(check.stdout)
        if backup:
            shutil.rmtree(backup)
        print(json.dumps({'installed': str(dest), 'config': str(cfg), 'python': str(py),
                          'codebuddy_found': True, 'authentication': 'not tested; models-refresh then models-probe',
                          'codex_cli_found': bool(shutil.which('codex')), 'doctor': health}, ensure_ascii=False))
    except Exception:
        if backup and backup.exists():
            if dest.exists():
                shutil.rmtree(dest)
            backup.rename(dest)
        elif published and dest.exists():
            shutil.rmtree(dest)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['install', 'update', 'uninstall'])
    p.add_argument('--skills-dir', type=Path, default=default_skills())
    p.add_argument('--state-dir', type=Path)
    a = p.parse_args()
    dest = a.skills_dir.expanduser().absolute() / 'codex-codebuddy'
    state_arg = a.state_dir
    if state_arg is None and a.action == 'update' and dest.exists():
        state_arg = Path(verify_owned(dest)['config']).parent
    state = (state_arg or default_state()).expanduser().absolute()
    # Config/history must survive uninstall and may never live under the Skill.
    if state == dest or dest in state.parents:
        raise SystemExit('state-dir must be outside installed Skill')
    try:
        if a.action == 'uninstall':
            if not dest.exists():
                print('Skill absent; nothing removed')
                return
            verify_owned(dest)
            shutil.rmtree(dest)
            print('Removed only owned Skill; config, jobs and history retained')
        else:
            install(dest, state, a.action == 'update')
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        raise SystemExit(str(e))

if __name__ == '__main__':
    main()
