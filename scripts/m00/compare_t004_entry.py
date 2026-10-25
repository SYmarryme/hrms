"""Compare loopback Vite vs public HTTPS. Observe attributes; never store cookies."""
import argparse
import json
import re
import ssl
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from t004_browser import attributes, set_cookie_attributes, strict
from t004_probe import NoRedirect

ROOT = Path(__file__).resolve().parents[2]
PATH = '/api/v1/poc/cookie'


def observe(base, host, name, probe_id, service_commit):
    # No HTTPCookieProcessor, credentials, redirects, TLS bypass or persisted jar.
    client = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    result = {'request_path': PATH}
    try:
        def get(path):
            request = Request(base + path, headers={'Host': host, 'User-Agent': 'HRMS-T004-Attribute-Compare/1', 'Cache-Control': 'no-cache'})
            with client.open(request, timeout=15) as response:
                if response.status != 200 or response.geturl() != base + path:
                    raise ValueError('Unexpected status or final URL')
                return json.loads(response.read(65536)), response.headers

        health, _ = get('/api/v1/poc/health')
        received_commit = health.get('commit')
        result['service_commit'] = received_commit if isinstance(received_commit, str) and re.fullmatch('[0-9a-f]{40}', received_commit) else None
        result['fixture_matches'] = health.get('fixture') == 'hrms-t004' and health.get('status') == 'ok'
        result['service_commit_matches'] = result['service_commit'] == service_commit
        payload, headers = get(PATH + '?probe_id=' + probe_id)
        result['backend'] = attributes(payload.get('backend_set_cookie'))
        result['vite_metadata'] = attributes(json.loads(headers.get('x-t004-vite-set-cookie') or 'null'))
        # Raw headers/values exist only transiently for parsing; output is whitelisted.
        result['received'] = [item for line in headers.get_all('Set-Cookie', [])
                              for item in set_cookie_attributes(line) if item['name'] == name]
    except Exception as error:
        result['error_type'] = type(error).__name__
        if isinstance(error, HTTPError):
            result['http_status'] = error.code
    return result


def compare(local, public, name):
    common = {'platform_globally_unsupported': 'NOT_ESTABLISHED',
              'formal_acceptance': 'NOT_GRANTED', 'real_browser_required': True}
    if any(item.get('error_type') or not item.get('fixture_matches') or not item.get('service_commit_matches') for item in (local, public)):
        return {**common, 'result': 'INCOMPLETE', 'boundary': 'SOURCE_OR_NETWORK_UNVERIFIED'}
    if not strict(local.get('backend'), name) or local.get('received') != [local.get('backend')]:
        return {**common, 'result': 'FAIL', 'boundary': 'LOCAL_APP_OR_VITE_CHAIN'}
    if not strict(public.get('backend'), name):
        return {**common, 'result': 'INCOMPLETE', 'boundary': 'PUBLIC_APP_EVIDENCE_DIFFERS'}
    if local.get('vite_metadata') is None or public.get('vite_metadata') is None:
        return {**common, 'result': 'INCOMPLETE', 'boundary': 'MISSING_VITE_METADATA'}
    if local['vite_metadata'] != local['backend']:
        return {**common, 'result': 'FAIL', 'boundary': 'LOCAL_APP_OR_VITE_CHAIN'}
    if public['vite_metadata'] != public['backend']:
        return {**common, 'result': 'FAIL', 'boundary': 'PUBLIC_APP_OR_VITE_CHAIN'}
    if not isinstance(public.get('received'), list) or len(public['received']) != 1:
        return {**common, 'result': 'INCOMPLETE', 'boundary': 'PUBLIC_COOKIE_RESPONSE_AMBIGUOUS'}
    if public.get('received') != local.get('received'):
        return {**common, 'result': 'BLOCKED_CURRENT_PUBLIC_ENTRY', 'boundary': 'AFTER_LOOPBACK_VITE',
                'note': 'Public response differs after loopback Vite; does not identify a specific vendor component'}
    return {**common, 'result': 'ATTRIBUTES_MATCH_FOR_THIS_CLIENT', 'boundary': 'NO_DIFFERENCE_IN_THIS_SAMPLE',
            'note': 'Does not clear the already reported Chromium failure or prove all client contexts compatible'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin', required=True, help='Existing bare public HTTPS origin')
    parser.add_argument('--service-commit', required=True, help='Actual commit of the ALREADY RUNNING service')
    args = parser.parse_args()
    (ROOT / 'var/m00').mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='t004-compat.', dir=ROOT / 'var/m00'))
    report = {'comparison_execution': 'NOT_RUN', 'client_scope': 'stdlib_attributes_only',
              'request_path': PATH, 'formal_T004_acceptance': 'NOT_GRANTED'}
    try:
        origin = urlsplit(args.origin)
        if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.path not in ('', '/') or origin.query or origin.fragment:
            raise ValueError('Bare HTTPS origin required')
        if not re.fullmatch('[0-9a-f]{40}', args.service_commit):
            raise ValueError('Actual service commit required')
        identifier = uuid.uuid4().hex
        name = 'hrms_t004_probe_' + identifier
        report['cookie_name'] = name
        report['expected_service_commit'] = args.service_commit
        report['script_commit'] = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
        report['comparison_execution'] = 'REQUESTS_ATTEMPTED'
        report['loopback_vite_3000'] = observe('http://127.0.0.1:3000', origin.netloc, name, identifier, args.service_commit)
        report['public_https'] = observe(args.origin.rstrip('/'), origin.netloc, name, identifier, args.service_commit)
        report['comparison'] = compare(report['loopback_vite_3000'], report['public_https'], name)
        code = 0 if report['comparison']['result'] == 'ATTRIBUTES_MATCH_FOR_THIS_CLIENT' else 1
    except Exception as error:
        report['comparison'] = {'result': 'INCOMPLETE', 'error_type': type(error).__name__}
        code = 1
    (folder / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (folder / 'exit-code.txt').write_text(str(code) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    print(f'T004_COMPAT_EXIT_CODE={code}; artifacts={folder}')
    sys.exit(code)
