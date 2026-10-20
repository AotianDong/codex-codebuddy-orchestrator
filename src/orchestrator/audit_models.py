"""Discover account-visible model credits over local ACP stdio, without inference."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from .runtime import cli_command, cli_version

BASE = Path(__file__).resolve().parent
IDS = ('deepseek-v4.1-flash', 'minimax-m3.1-flash')


def discover(node, cli, directory):
    directory.mkdir(parents=True, exist_ok=True)
    inbox = queue.Queue()
    argv = cli_command(node, cli) + ['--acp', '--tools', '', '--strict-mcp-config', '--mcp-config',
            '{"mcpServers":{}}', '--setting-sources', '', '--no-session-persistence']
    errors = directory / 'catalog.stderr'
    messages = []
    with errors.open('wb') as fe:
        proc = subprocess.Popen(argv, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=fe, creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name == 'nt' else 0)
        def reader():
            for line in proc.stdout:
                try:
                    inbox.put(json.loads(line))
                except ValueError:
                    pass
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        def request(number, method, params):
            proc.stdin.write((json.dumps({'jsonrpc': '2.0', 'id': number, 'method': method,
                                         'params': params}) + '\n').encode('utf-8'))
            proc.stdin.flush()
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                message = inbox.get(timeout=max(0.1, deadline - time.monotonic()))
                messages.append(message)
                if message.get('id') == number:
                    if 'error' in message:
                        raise RuntimeError(str(message['error']))
                    return message['result']
            raise TimeoutError(method)
        try:
            initialized = request(1, 'initialize', {'protocolVersion': 1, 'clientCapabilities': {},
                                  'clientInfo': {'name': 'local-cost-audit', 'version': '2'}})
            session = request(2, 'session/new', {'cwd': str(directory), 'mcpServers': []})
        finally:
            proc.kill()
            proc.wait(timeout=15)
            proc.stdin.close()
            proc.stdout.close()
    found = {}
    def walk(value):
        if isinstance(value, dict):
            mid = value.get('modelId', value.get('id', value.get('value')))
            if mid in IDS:
                found.setdefault(mid, []).append({k: value[k] for k in
                    ('modelId', 'id', 'value', 'name', 'description', '_meta') if k in value})
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    walk(session)
    package = Path(cli).parent.parent / 'package.json'
    report = {'verified_at': datetime.now(timezone.utc).isoformat(),
              'source_kind': 'cli_acp_account_catalog',
              'source': 'installed CLI ACP session/new account-visible catalog; no session/prompt sent',
              'official_docs': 'https://www.codebuddy.cn/docs/cli/acp',
              'cli_version': cli_version(cli, node),
              'cli_entry_sha256': hashlib.sha256(Path(cli).read_bytes()).hexdigest(),
              'agent_info': initialized.get('agentInfo'), 'models': found,
              'inference_calls': 0}
    (directory / 'catalog.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report
