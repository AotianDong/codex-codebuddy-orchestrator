"""Scan Git publish candidates, not ignored local state. Findings contain no secret values."""
from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    ('private_key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('provider_token', re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9]{24,})')),
    ('assigned_secret', re.compile(r'(?im)^\s*["\x27]?(?:api[_-]?key|access[_-]?token|authorization|cookie)["\x27]?\s*[:=]\s*["\x27]?[A-Za-z0-9/+_.=-]{20,}')),
    ('personal_windows_path', re.compile(r'(?i)[A-Z]:[\\/]+Users[\\/]+(?!<|\$|%)[^\s\\/"\x27]+[\\/]')),
    ('personal_posix_path', re.compile(r'/(?:Users|home)/(?!<|\$)[A-Za-z0-9_.-]+/'))
]

def scan(root=ROOT):
    raw = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
    findings = []
    names = sorted(set(x.decode('utf-8') for x in raw.split(b'\0') if x))
    for name in names:
        p = root / name
        if not p.is_file():
            continue
        if any(part in {'.codebuddy', '.workbuddy', 'catalog', 'probes', 'jobs'} for part in p.relative_to(root).parts):
            findings.append({'file': name, 'kind': 'private_artifact'})
        text = p.read_text('utf-8', errors='replace')
        for kind, pattern in PATTERNS:
            if pattern.search(text):
                findings.append({'file': name, 'kind': kind})
    return {'files_scanned': len(names), 'findings': findings,
            'limitation': 'Pattern scan is not a proof that no sensitive information exists; review staged diff.'}

if __name__ == '__main__':
    result = scan()
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result['findings']))
