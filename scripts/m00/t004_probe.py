"""Stdlib HTTP/TLS/cookie/forwarding probe; never prints cookies or raw responses."""
import argparse
import http.cookiejar
import json
import re
import ssl
import sys
import tempfile
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def probe(origin, expected_commit, local, outside_canary=None):
    parsed = urlsplit(origin)
    assert not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
    assert parsed.path in ('', '/')
    if local:
        assert origin == 'http://127.0.0.1:8000', 'Local mode only probes the loopback backend'
    else:
        assert parsed.scheme == 'https' and parsed.hostname, 'Public probe requires a bare HTTPS origin'
        assert parsed.hostname not in ('localhost', '127.0.0.1', '::1')
    origin = origin.rstrip('/')
    jar = http.cookiejar.CookieJar()
    client = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()),
                          HTTPCookieProcessor(jar), NoRedirect())
    checks = []

    def check(name, ok):
        checks.append({'check': name, 'result': 'PASS' if ok else 'FAIL'})
        assert ok, name

    def get(path, headers=None):
        with client.open(Request(origin + path, headers=headers or {}), timeout=15) as response:
            assert response.status == 200
            return json.loads(response.read(32768)), response.headers

    spoof = {'Forwarded': 'for=192.0.2.1;proto=http;host=invalid.example',
             'X-Forwarded-Proto': 'http', 'X-Forwarded-Host': 'invalid.example',
             'X-Forwarded-For': '192.0.2.1', 'X-Forwarded-Port': '80'}
    health, _ = get('/api/v1/poc/health', spoof)
    check('health_and_commit', health.get('fixture') == 'hrms-t004' and health.get('status') == 'ok' and health.get('commit') == expected_commit)
    check('uvicorn_does_not_trust_forwarded_scheme', health.get('transport_scheme') == 'http')
    if local:
        check('local_forged_headers_not_authoritative', not health.get('forwarded_proto_https') and not health.get('forwarded_host_matches'))
    else:
        check('proxy_replaces_untrusted_forwarding', health.get('forwarded_proto_https') is True and health.get('forwarded_host_matches') is True
              and health.get('forwarded_present') is False and health.get('forwarded_for_present') is False)
        _, headers = get('/api/v1/poc/cookie')
        cookie = SimpleCookie()
        for value in headers.get_all('Set-Cookie', []):
            cookie.load(value)
        marker = cookie.get('hrms_t004_probe')
        check('cookie_attributes', marker is not None and bool(marker['secure']) and bool(marker['httponly'])
              and marker['path'] == '/api/v1/poc/' and marker['samesite'].lower() == 'lax' and not marker['domain'])
        inside, _ = get('/api/v1/poc/cookie-check')
        outside, _ = get('/api/v1/poc-outside/cookie-check')
        check('cookie_inside_path', inside.get('received') is True)
        check('cookie_outside_path', outside.get('received') is False)
        if outside_canary:
            canary = Path(outside_canary)
            assert canary.is_absolute(), 'Canary must be the actual absolute CloudStudio path'
            check('canary_exists_with_expected_marker', canary.is_file() and canary.read_text(encoding='utf-8') == 't004-outside-should-not-serve\n')
            try:
                client.open(origin + '/@fs/' + quote(outside_canary, safe='/'), timeout=15).close()
            except HTTPError as error:
                check('vite_outside_root_denied', error.code in (403, 404))
            else:
                check('vite_outside_root_denied', False)
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--local', action='store_true')
    parser.add_argument('--outside-canary', help='Actual CloudStudio ENV_DIR/outside-canary.txt path')
    args = parser.parse_args()
    (ROOT / 'var/m00').mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='t004-probe.', dir=ROOT / 'var/m00'))
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'commit': args.commit,
              'scope': 'local' if args.local else 'public_https',
              'browser': 'NOT_RUN', 'external_8000': 'NOT_RUN', 'workspace_restart': 'NOT_RUN'}
    try:
        assert re.fullmatch('[0-9a-f]{40}', args.commit), 'Invalid expected Git commit'
        report['checks'] = probe(args.origin, args.commit, args.local, args.outside_canary)
        report['filesystem_boundary'] = 'CHECKED' if args.outside_canary and not args.local else 'NOT_RUN'
        report['result'] = 'PASS'
        code = 0
    except (AssertionError, OSError, ValueError, HTTPError, URLError) as error:
        # No response bodies, request headers, cookie jars or credential-bearing URLs.
        report.update(result='FAIL', error_type=type(error).__name__)
        if isinstance(error, HTTPError):
            report['http_status'] = error.code
        if isinstance(error, AssertionError):
            report['failed_assertion'] = str(error)
        code = 1
    (folder / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (folder / 'exit-code.txt').write_text(str(code) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    print(f'T004_PROBE_EXIT_CODE={code}; artifacts={folder}')
    sys.exit(code)
