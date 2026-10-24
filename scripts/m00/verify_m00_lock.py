"""Strict installed-distribution and optional JUnit check for the Ubuntu replay."""
import argparse
import importlib.metadata
import json
import platform
import re
import site
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def canonical(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def read_pins(path):
    pins = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)', line)
        if not match:
            raise ValueError(f'Not an exact version pin in {path.name}: {line}')
        name = canonical(match[1])
        if name in pins:
            raise ValueError(f'Duplicate lock entry: {name}')
        pins[name] = match[2]
    return pins


def verify(venv, junit=None):
    tools = read_pins(ROOT / 'requirements/m00-bootstrap.lock')
    project = read_pins(ROOT / 'requirements/m00.lock')
    if set(tools) != {'pip', 'setuptools'} or tools.keys() & project.keys():
        raise ValueError('Bootstrap/project lock separation is invalid')
    expected = tools | project
    actual = {}
    for distribution in importlib.metadata.distributions():
        name = canonical(distribution.metadata['Name'])
        if name in actual:
            raise ValueError(f'Duplicate installed distribution: {name}')
        actual[name] = distribution.version
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    mismatched = {name: {'expected': expected[name], 'actual': actual[name]}
                  for name in expected.keys() & actual.keys()
                  if actual[name] != expected[name]}
    isolated = (Path(sys.prefix).resolve() == venv.resolve()
                and sys.prefix != sys.base_prefix and not site.ENABLE_USER_SITE)
    errors = []
    if platform.python_version() != '3.11.1':
        errors.append('Exact replay requires Python 3.11.1')
    if not isolated:
        errors.append('Interpreter is not the requested isolated venv')
    if missing or extra or mismatched:
        errors.append('Installed distributions differ from lock union')
    report = {
        'python': platform.python_version(), 'isolated_venv': isolated,
        'bootstrap': tools, 'project': project, 'installed': dict(sorted(actual.items())),
        'missing': missing, 'extra': extra, 'mismatched': mismatched,
        'poc': 'NOT_RUN', 'errors': errors,
    }
    if junit is not None:
        root = ET.parse(junit).getroot()
        cases = root.findall('.//testcase')
        bad = [case.attrib.get('name') for case in cases
               if any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped'))]
        # Refuse a truncated/empty suite or unassociated JUnit-level errors.
        if len(cases) != 13 or bad or root.findall('.//error') or root.findall('.//failure') or root.findall('.//skipped'):
            errors.append('PoC requires exactly 13 passed, zero failed/errors/skipped')
        report['poc'] = {'cases': len(cases), 'not_passed': bad,
                         'result': 'PASS' if not errors else 'FAIL'}
    report['result'] = 'LOCK_MATCH' if not errors else 'FAIL'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--venv', required=True, type=Path)
    parser.add_argument('--junit', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.venv, args.junit)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=2))
        sys.exit(bool(result['errors']))
    except (OSError, ValueError, ET.ParseError) as error:
        print(f'REPLAY_VERIFICATION_FAIL: {error}', file=sys.stderr)
        sys.exit(1)
