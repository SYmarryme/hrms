"""Observe T-004 listeners/HTTPS reachability without cookies or raw responses.

Negative network observations never grant external isolation acceptance.
Run on CloudStudio Ubuntu; no services or platform mappings are changed.
"""
import argparse
import ipaddress
import json
import re
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from t004_probe import NoRedirect

ROOT = Path(__file__).resolve().parents[2]
HEALTH = '/api/v1/poc/health'


def health(origin, expected_commit):
    client = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    result = {'path': HEALTH, 'fixture_matches': False, 'service_commit_matches': False}
    try:
        request = Request(origin + HEALTH, headers={'Cache-Control': 'no-cache', 'User-Agent': 'HRMS-T004-Isolation/1'})
        with client.open(request, timeout=15) as response:
            result['http_status'] = response.status
            payload = json.loads(response.read(16384))
            # Deliberately project only booleans; never write response/header values.
            result['fixture_matches'] = isinstance(payload, dict) and payload.get('fixture') == 'hrms-t004'
            result['healthy'] = result['fixture_matches'] and payload.get('status') == 'ok'
            result['service_commit_matches'] = result['fixture_matches'] and payload.get('commit') == expected_commit
    except Exception as error:
        result['error_type'] = type(error).__name__
        if isinstance(error, HTTPError):
            result['http_status'] = error.code
    return result


def bare_https(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Bare HTTPS origin required')
    return value.rstrip('/')


def local_observation(commit):
    raw = subprocess.check_output(['ss', '-H', '-ltn'], text=True)
    listeners = {3000: [], 8000: []}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) < 5:
            raise ValueError('Unexpected ss output')
        address, separator, port = fields[3].rpartition(':')
        if separator and port in ('3000', '8000'):
            listeners[int(port)].append(address.strip('[]'))
    def is_loopback(address):
        try:
            return ipaddress.ip_address(address).is_loopback
        except ValueError:
            return False  # A wildcard/unrecognized listener cannot satisfy isolation.

    loopback_only = bool(listeners[8000]) and all(is_loopback(address) for address in listeners[8000])
    probe = health('http://127.0.0.1:8000', commit)
    ok = loopback_only and bool(listeners[3000]) and probe.get('healthy') and probe['service_commit_matches']
    return {'result': 'LOCAL_BINDING_OK' if ok else 'FAIL_LOCAL_PRECONDITION',
            'listeners': {str(port): addresses for port, addresses in listeners.items()},
            'backend_loopback_only': loopback_only, 'backend_health': probe,
            'external_isolation': 'NOT_VERIFIED'}, 0 if ok else 1


def remote_observation(frontend, backend, commit):
    control = health(frontend, commit)
    probe = health(backend, commit)
    if probe['fixture_matches']:
        result, code = 'FAIL_BACKEND_EXTERNALLY_ROUTABLE', 1
    elif not control.get('healthy') or not control['service_commit_matches']:
        result, code = 'INCOMPLETE_POSITIVE_CONTROL', 2
    else:
        result, code = 'OBSERVATION_ONLY_EXTERNAL_EVIDENCE_REQUIRED', 2
    return {'result': result, 'vantage': 'WORKSPACE_EGRESS_UNLESS_OPERATOR_RUNS_ELSEWHERE',
            'frontend_positive_control': control, 'backend_candidate': probe,
            'external_isolation': 'NOT_VERIFIED',
            'note': 'HTTP denial, redirect, DNS/TLS/timeout or unrelated page alone cannot prove isolation'}, code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['local', 'remote'])
    parser.add_argument('--service-commit', required=True)
    parser.add_argument('--origin', help='Existing 3000 HTTPS origin')
    parser.add_argument('--backend-origin', help='Existing/documented 8000 HTTPS origin; never create a new mapping')
    args = parser.parse_args()
    (ROOT / 'var/m00').mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='t004-isolation.', dir=ROOT / 'var/m00'))
    report = {'formal_T004_acceptance': 'NOT_GRANTED', 'action': args.action}
    try:
        if not re.fullmatch('[0-9a-f]{40}', args.service_commit):
            raise ValueError('Actual running service commit required')
        report['script_commit'] = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
        report['expected_service_commit'] = args.service_commit
        if args.action == 'local':
            observation, code = local_observation(args.service_commit)
        else:
            frontend = bare_https(args.origin or '')
            backend = bare_https(args.backend_origin or '')
            front_host, back_host = urlsplit(frontend).hostname, urlsplit(backend).hostname
            # Official URL pattern: same workspace/region/domain, only --PORT differs.
            if not front_host.split('.')[0].endswith('--3000') or back_host != front_host.replace('--3000.', '--8000.', 1):
                raise ValueError('Origins must be the same documented workspace entry with --3000/--8000; other formats need official confirmation')
            observation, code = remote_observation(frontend, backend, args.service_commit)
        report.update(observation)
    except Exception as error:
        report.update(result='INCOMPLETE', error_type=type(error).__name__)
        code = 2
    (folder / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (folder / 'exit-code.txt').write_text(str(code) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    print(f'T004_ISOLATION_EXIT_CODE={code}; artifacts={folder}')
    return code


if __name__ == '__main__':
    sys.exit(main())
