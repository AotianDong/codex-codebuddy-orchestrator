"""Discover a native CodeBuddy binary or npm entry without executing shell shims."""
import json
import os
from pathlib import Path
import shutil
import subprocess

def discover_cli():
    node = os.environ.get('CBO_NODE') or shutil.which('node') or ''
    configured = os.environ.get('CBO_CLI')
    candidate = configured or shutil.which('codebuddy') or shutil.which('cbc') or ''
    if candidate:
        p = Path(candidate).expanduser().resolve()
        # npm shims on Windows and global bin symlinks on POSIX.
        for entry in (p.parent / 'node_modules/@tencent-ai/codebuddy-code/bin/codebuddy',
                      p.parent.parent / 'lib/node_modules/@tencent-ai/codebuddy-code/bin/codebuddy'):
            if entry.is_file():
                return node, str(entry)
        return node, str(p)
    return node, ''

def cli_command(node, cli):
    p = Path(cli)
    if not cli or not p.is_absolute() or not p.is_file():
        raise ValueError('CodeBuddy not found. Install CLI or configure absolute codebuddy_cli.')
    if p.suffix.lower() in ('.cmd', '.bat', '.ps1'):
        raise ValueError('Configure npm JS entry plus node_path, or a native binary; shell shims are not executed.')
    if (p.parent.parent / 'package.json').is_file() or p.suffix in ('.js', '.mjs', '.cjs'):
        if not node or not Path(node).is_file():
            raise ValueError('Node.js is required for the npm CLI')
        return [str(node), str(p)]
    return [str(p)]

def cli_version(cli, node=None):
    package = Path(cli).parent.parent / 'package.json'
    if package.is_file():
        return json.loads(package.read_text('utf-8'))['version']
    p = subprocess.run(cli_command(node or discover_cli()[0], cli) + ['--version'],
                       capture_output=True, text=True, timeout=15, check=True)
    return p.stdout.strip()
