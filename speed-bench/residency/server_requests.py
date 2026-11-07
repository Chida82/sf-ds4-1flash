#!/usr/bin/env python3
"""Two chat requests to a running server, as a long-lived session sees them: request A (a prompt and a long
answer), then request B (an unrelated prompt). Prints one JSON line per request: prompt tokens, how many came
from the server's cache, time to first token and the completion size. Hooks run between A and B.

    python3 speed-bench/residency/server_requests.py --port 8002 --a-tokens 2000 [--between CMD] [--before-b CMD]

The prompts are slices of speed-bench/promessi_sposi.txt far apart, so B shares only the chat template with A."""
import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / 'speed-bench/promessi_sposi.txt').read_text()


def ask(port, prompt, max_tokens):
    body = json.dumps({'model': 'deepseek-v4.1-flash', 'stream': True, 'stream_options': {'include_usage': True},
                       'max_tokens': max_tokens, 'temperature': 0,
                       'messages': [{'role': 'user', 'content': prompt}]}).encode()
    req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions', body,
                                 {'Content-Type': 'application/json'})
    t0, first, usage, chunks = time.time(), None, None, 0
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith('data: ') or line == 'data: [DONE]':
                continue
            ev = json.loads(line[6:])
            if ev.get('usage'):
                usage = ev['usage']
            delta = (ev.get('choices') or [{}])[0].get('delta', {})
            if delta.get('content') or delta.get('reasoning_content'):
                chunks += 1
                if first is None:
                    first = time.time()
    return {'ttft_s': round((first or time.time()) - t0, 3), 'total_s': round(time.time() - t0, 3),
            'prompt_tokens': usage and usage['prompt_tokens'],
            'cached_tokens': usage and usage['prompt_tokens_details']['cached_tokens'],
            'completion_tokens': usage and usage['completion_tokens'], 'chunks': chunks}


p = argparse.ArgumentParser()
p.add_argument('--port', type=int, default=8002)
p.add_argument('--a-tokens', type=int, default=2000)
p.add_argument('--chars', type=int, default=7000, help='characters per prompt slice (about 2048 tokens)')
p.add_argument('--between', help='shell command run after A (e.g. other file reads)')
p.add_argument('--before-b', help='shell command run right before B (e.g. a snapshot)')
args = p.parse_args()
a = 'Riassumi in modo molto dettagliato, capitolo per capitolo, il testo seguente.\n\n' + TEXT[:args.chars]
mid = len(TEXT) // 2
b = 'Di quali personaggi parla questo brano?\n\n' + TEXT[mid:mid + args.chars]
print(json.dumps({'request': 'A', **ask(args.port, a, args.a_tokens)}), flush=True)
if args.between:
    subprocess.run(args.between, shell=True, check=True)
if args.before_b:
    subprocess.run(args.before_b, shell=True, check=True)
print(json.dumps({'request': 'B', 'time': time.time(), **ask(args.port, b, 16)}), flush=True)
