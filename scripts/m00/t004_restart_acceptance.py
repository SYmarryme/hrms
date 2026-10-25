"""Wrap existing SQLite marker checks with an independently retained receipt hash.

Content verification cannot prove a CloudStudio UI workspace restart occurred.
No databases are restored, and no application/environment is restarted here.
"""
import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

from t004_persistence import ROOT, prepare, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['before', 'after'])
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--receipt-sha256')
    args = parser.parse_args()
    (ROOT / 'var/m00').mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='t004-restart.', dir=ROOT / 'var/m00'))
    report = {'formal_T004_acceptance': 'NOT_GRANTED', 'action': args.action,
              'workspace_restart': 'MANUAL_EVIDENCE_REQUIRED'}
    try:
        if not __debug__:
            raise RuntimeError('Original SQLite verifier assertions must be enabled')
        if args.action == 'before':
            if args.data_root is None:
                raise ValueError('Existing absolute data-root required')
            # Only ignored workspace data is accepted; never place an experiment in served sources.
            data_root = args.data_root.resolve()
            if not args.data_root.is_absolute() or not data_root.is_relative_to((ROOT / 'var/m00').resolve()):
                raise ValueError('Data root must be inside ignored var/m00')
            receipt = folder / 'receipt.json'
            receipt.write_text(json.dumps(prepare(data_root), indent=2) + '\n', encoding='utf-8')
            baseline = verify(receipt)
            report.update(result='BASELINE_READY', receipt=str(receipt),
                          receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
                          baseline=baseline, workspace_restart='NOT_RUN')
        else:
            if args.receipt is None or not args.receipt.is_absolute() or not re.fullmatch('[0-9a-f]{64}', args.receipt_sha256 or ''):
                raise ValueError('Absolute original receipt and independently retained pre-restart SHA-256 required')
            if hashlib.sha256(args.receipt.read_bytes()).hexdigest() != args.receipt_sha256:
                raise ValueError('Receipt differs from pre-restart copy')
            checked = verify(args.receipt)
            report.update(result='CONTENT_MATCH', verification=checked,
                          receipt_sha256=args.receipt_sha256)
        code = 0
    except Exception as error:
        report.update(result='FAIL', error_type=type(error).__name__,
                      instruction='Do not prepare a replacement database or restore a backup; preserve private evidence')
        code = 1
    (folder / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (folder / 'exit-code.txt').write_text(str(code) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    print(f'T004_RESTART_EXIT_CODE={code}; artifacts={folder}')
    return code


if __name__ == '__main__':
    sys.exit(main())
