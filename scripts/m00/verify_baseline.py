"""Verify the private handoff against its manifest AND the frozen public index."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def verify(handoff: Path) -> None:
    pinned = json.loads((ROOT / 'docs/baseline-sha256.json').read_text(encoding='utf-8'))
    manifest = handoff / 'SHA256_七份正式文档.txt'
    entries = {}
    for line in manifest.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        match = re.fullmatch(r'([a-f0-9]{64})  (.+)', line)
        if not match or match[2] in entries:
            raise ValueError('Malformed or duplicate manifest entry')
        entries[match[2]] = match[1]
    if len(entries) != 7 or entries != pinned:
        raise ValueError('Manifest differs from the approved seven-file index')
    for relative, expected in entries.items():
        path = (handoff / relative).resolve()
        if not path.is_relative_to(handoff.resolve()):
            raise ValueError('Manifest path escapes handoff')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'SHA-256 mismatch: {relative}')
        print(f'MATCH {relative} {expected}')
    print('BASELINE_HASH_MATCH: 7/7; this is not cloud runtime acceptance')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--handoff', type=Path, default=ROOT / 'handoff/hrms-m00')
    args = parser.parse_args()
    try:
        verify(args.handoff)
    except (OSError, ValueError) as error:
        print(f'BASELINE_FAIL: {error}', file=sys.stderr)
        sys.exit(1)
