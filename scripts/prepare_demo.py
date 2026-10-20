import argparse
import json
from pathlib import Path
import shutil
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from orchestrator import scheduler as s
p = argparse.ArgumentParser()
p.add_argument('destination', type=Path)
a = p.parse_args()
repo = a.destination.expanduser().resolve()
if repo.exists():
    raise SystemExit('Destination exists; refusing overwrite')
shutil.copytree(ROOT / 'examples/demo-project', repo)
s.git(repo, 'init', '-q')
s.git(repo, 'add', '--all')
s.git(repo, '-c', 'user.name=Demo', '-c', 'user.email=demo@localhost', 'commit', '-qm', 'demo baseline')
task = json.loads((ROOT / 'examples/task.example.json').read_text('utf-8'))
task['repository'] = str(repo)
manifest = repo.with_name(repo.name + '.task.json')
if manifest.exists():
    raise SystemExit('Task manifest already exists')
s.write_json(manifest, task)
print(manifest)
