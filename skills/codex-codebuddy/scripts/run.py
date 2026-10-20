"""Portable installed entrypoint; no checkout or global package install required."""
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True
base = Path(__file__).resolve().parent
sys.path.insert(0, str(base / 'runtime'))
from orchestrator.dispatcher import main
arguments = sys.argv[1:]
if '--config' not in arguments:
    arguments = ['--config', json.loads((base / 'local.json').read_text('utf-8'))['config'], *arguments]
raise SystemExit(main(arguments))
