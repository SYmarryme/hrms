"""Real Chromium wire diagnostics. Never persist raw headers, cookie values or HAR."""
import argparse
import json
import re
import sys
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

PREFIX = 'hrms_t004_probe_'
NAME = re.compile(r'^hrms_t004_probe_[0-9a-f]{32}$')
BASE = '/api/v1/poc/'
ISSUE = BASE + 'cookie'
INSIDE = BASE + 'cookie-check'
OUTSIDE = '/api/v1/poc-outside/cookie-check'
FRAME = BASE + 'browser-cookie'
PATHS = (ISSUE, INSIDE, OUTSIDE, FRAME)


def header(headers, name):
    return next((str(value) for key, value in headers.items() if key.lower() == name), '')


def name_counts(raw):
    result = {}
    for part in raw.split(';'):
        name = part.partition('=')[0].strip()
        if NAME.fullmatch(name):
            result[name] = result.get(name, 0) + 1
    return result


def attributes(data):
    if not isinstance(data, dict) or not NAME.fullmatch(str(data.get('name', ''))):
        return None
    path = data.get('path')
    if not isinstance(path, str) or len(path) > 512 or any(char in path for char in ('\r', '\n', '\x00')):
        return None
    if path and not path.startswith('/'):
        path = '<invalid-path>'
    same_site = str(data.get('sameSite', '')).lower()
    return {'name': data['name'], 'path': path, 'secure': data.get('secure') is True,
            'httpOnly': data.get('httpOnly') is True,
            'sameSite': same_site if same_site in ('lax', 'strict', 'none') else 'unspecified',
            'domain_present': data.get('domain_present') if type(data.get('domain_present')) is bool else None}


def set_cookie_attributes(raw):
    result = []
    for line in raw.splitlines():
        parsed = SimpleCookie()
        try:
            parsed.load(line)
        except CookieError:
            continue
        for name, marker in parsed.items():
            if NAME.fullmatch(name):
                result.append(attributes({'name': name, 'path': marker['path'],
                    'secure': bool(marker['secure']), 'httpOnly': bool(marker['httponly']),
                    'sameSite': marker['samesite'], 'domain_present': bool(marker['domain'])}))
    return [item for item in result if item is not None]


def safe_boundary(data):
    if not isinstance(data, dict):
        return {}
    proxy = data.get('proxy') if isinstance(data.get('proxy'), dict) else {}
    def path(value):
        if isinstance(value, str) and value.startswith('/') and len(value) <= 512 and not any(char in value for char in ('\r', '\n', '\x00', '?', '#')):
            return value
        return 'OTHER_OR_MISSING_PATH'

    paths = {key: path(data.get(key))
             for key in ('request_path', 'response_path', 'backend_path')}
    return {**paths, 'cookie_name': data.get('cookie_name') if NAME.fullmatch(str(data.get('cookie_name', ''))) else None,
        'backend_count': data.get('backend_count') if type(data.get('backend_count')) is int else None,
        'proxy': {
            'ingress_path': path(proxy.get('ingress_path')),
            'outgoing_path': path(proxy.get('outgoing_path')),
            'ingress_count': proxy.get('ingress_count') if type(proxy.get('ingress_count')) is int else None,
            'outgoing_count': proxy.get('outgoing_count') if type(proxy.get('outgoing_count')) is int else None}}


def strict(data, name):
    return data == {'name': name, 'path': BASE, 'secure': True, 'httpOnly': True,
                    'sameSite': 'lax', 'domain_present': False}


def classify(report):
    """Return observations, not guesses. Missing evidence ALWAYS prevents success."""
    findings = []
    name = report.get('cookie_name')
    records = report.get('requests', [])
    issuer = next((row for row in records if row['path'] == ISSUE), {})
    outside = next((row for row in records if row['path'] == OUTSIDE), {})
    inside = next((row for row in records if row['path'] == INSIDE), {})
    if not NAME.fullmatch(str(name)) or len(records) != 4 or any(
            sum(row['path'] == path for row in records) != 1 for path in PATHS):
        findings.append('INCOMPLETE_REQUEST_TRACE')
    if any(not row.get('wire_observed') or not row.get('response_observed') or row.get('redirected') for row in records):
        findings.append('INCOMPLETE_OR_REDIRECTED_WIRE_EVIDENCE')
    backend = report.get('backend_set_cookie')
    vite = report.get('vite_set_cookie')
    received = issuer.get('response_cookies', [])
    if not strict(backend, name):
        findings.append('BACKEND_COOKIE_ATTRIBUTES_MISMATCH')
    if vite is None or not received:
        findings.append('MISSING_RESPONSE_BOUNDARY')
    elif backend != vite:
        findings.append('BACKEND_TO_VITE_COOKIE_TRANSFORM')
    elif received != [vite]:
        findings.append('EDGE_SET_COOKIE_TRANSFORM')
    for row in records:
        # A later response may reissue the marker, so inspect ALL four responses.
        if row.get('path') != ISSUE and row.get('response_cookies'):
            findings.append('COOKIE_REISSUED_AFTER_ISSUANCE')
        boundary = row.get('boundary', {})
        proxy = boundary.get('proxy', {})
        if row['path'] in (INSIDE, OUTSIDE):
            if boundary.get('cookie_name') != name:
                findings.append('PROBE_NAME_MISMATCH')
            counts = (row.get('browser_count'), proxy.get('ingress_count'), proxy.get('outgoing_count'), boundary.get('backend_count'))
            if any(type(count) is not int for count in counts):
                findings.append('MISSING_REQUEST_BOUNDARY')
                continue
            if row['path'] != proxy.get('ingress_path'):
                findings.append('EDGE_REQUEST_PATH_TRANSFORM')
            if proxy.get('ingress_path') != proxy.get('outgoing_path'):
                findings.append('VITE_REQUEST_PATH_TRANSFORM')
            if proxy.get('outgoing_path') != boundary.get('backend_path'):
                findings.append('VITE_TO_BACKEND_PATH_TRANSFORM')
            if counts[0] != counts[1]:
                findings.append('EDGE_REQUEST_COOKIE_TRANSFORM')
            if counts[1] != counts[2]:
                findings.append('VITE_REQUEST_COOKIE_TRANSFORM')
            if counts[2] != counts[3]:
                findings.append('VITE_TO_BACKEND_OR_COUNTER_MISMATCH')
    stored = report.get('stored_cookies', [])
    if len(stored) != 1 or any(item.get('path') != BASE or not item.get('secure') or not item.get('httpOnly') or item.get('sameSite') != 'lax' for item in stored):
        findings.append('BROWSER_EFFECTIVE_SCOPE_OR_ATTRIBUTES_MISMATCH')
    if type(outside.get('browser_count')) is int and outside['browser_count'] > 0:
        effective = [item for item in outside.get('associated_cookies', []) if not item.get('blocked')]
        if not effective:
            findings.append('BROWSER_SEND_OBSERVED_EFFECTIVE_SCOPE_UNKNOWN')
        elif any(item.get('path') != BASE for item in effective):
            findings.append('BROWSER_SENT_COOKIE_WITH_DIFFERENT_EFFECTIVE_PATH')
        elif strict(vite, name) and received == [vite]:
            findings.append('BROWSER_SENT_STRICT_PATH_COOKIE_OUTSIDE_PATH')
    ui = report.get('ui', {})
    if (ui.get('outside_count') != outside.get('boundary', {}).get('backend_count')
            or ui.get('outside_diagnostic_count') != outside.get('boundary', {}).get('backend_count')):
        findings.append('FRONTEND_COUNTER_MISMATCH')
    if inside.get('browser_count') != 1 or outside.get('browser_count') != 0:
        findings.append('BROWSER_PATH_ISOLATION_FAILED')
    frame = next((row for row in records if row['path'] == FRAME), {})
    if frame.get('browser_count') != 1:
        findings.append('BROWSER_PATH_CONTEXT_COOKIE_MISSING')
    if ui.get('browser_result') != 'PASS':
        findings.append('BROWSER_UI_ASSERTIONS_FAILED')
    return sorted(set(findings))


def run(origin, commit):
    from playwright.sync_api import sync_playwright
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('A bare HTTPS origin is required')
    report = {'result': 'FAIL', 'requests': [], 'commit': commit}
    requests, extras, responses, bodies = {}, {}, {}, {}
    with sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(ignore_https_errors=False, service_workers='block')
        page = context.new_page()
        cdp = context.new_cdp_session(page)

        def request_seen(event):
            key = event['requestId']
            if key in requests:
                # A redirect may leave our path allowlist. Never mix its hops.
                requests[key]['redirected'] = True
                extras.pop(key, None)
                responses.pop(key, None)
                return
            url = urlsplit(event['request']['url'])
            identifier = parse_qs(url.query).get('probe_id', [''])[0]
            if url.path not in PATHS or not re.fullmatch('[0-9a-f]{32}', identifier):
                return
            requests[key] = {'path': url.path, 'name': PREFIX + identifier,
                'redirected': 'redirectResponse' in event}

        def request_extra(event):
            # Sanitize immediately, including when ExtraInfo precedes requestSeen.
            if requests.get(event['requestId'], {}).get('redirected'):
                return
            associated = []
            for item in event.get('associatedCookies', []):
                safe = attributes(item.get('cookie'))
                if safe:
                    associated.append({**safe, 'blocked': bool(item.get('blockedReasons'))})
            extras[event['requestId']] = {'counts': name_counts(header(event.get('headers', {}), 'cookie')), 'associated': associated}

        def response_extra(event):
            if requests.get(event['requestId'], {}).get('redirected'):
                return
            responses[event['requestId']] = set_cookie_attributes(header(event.get('headers', {}), 'set-cookie'))

        def response_seen(response):
            # Independently capture JSON before the page can miscompute its display.
            url = urlsplit(response.url)
            identifier = parse_qs(url.query).get('probe_id', [''])[0]
            if url.path not in (ISSUE, INSIDE, OUTSIDE) or not re.fullmatch('[0-9a-f]{32}', identifier):
                return
            name = PREFIX + identifier
            try:
                payload = response.json()
                if url.path == ISSUE:
                    bodies[(name, url.path)] = {'backend': attributes(payload.get('backend_set_cookie')),
                        'vite': attributes(json.loads(response.header_value('x-t004-vite-set-cookie') or 'null'))}
                else:
                    bodies[(name, url.path)] = safe_boundary({'request_path': url.path, 'response_path': url.path,
                        'cookie_name': payload.get('cookie_name'), 'backend_path': payload.get('observed_path'),
                        'backend_count': payload.get('cookie_name_count'), 'proxy': payload.get('proxy')})
            except Exception:
                bodies[(name, url.path)] = {}

        cdp.on('Network.requestWillBeSent', request_seen)
        cdp.on('Network.requestWillBeSentExtraInfo', request_extra)
        cdp.on('Network.responseReceivedExtraInfo', response_extra)
        page.on('response', response_seen)
        cdp.send('Network.enable')
        cdp.send('Network.setCacheDisabled', {'cacheDisabled': True})
        page.goto(origin, wait_until='domcontentloaded', timeout=30000)
        page.get_by_role('heading', name='HRMS T-004 健康检查', exact=True).wait_for(timeout=15000)
        page.get_by_role('button', name='运行浏览器同源与 Cookie 检查', exact=True).click()
        page.wait_for_function("() => { try { return ['PASS','FAIL'].includes(JSON.parse(document.querySelector('pre').textContent).browser_result); } catch { return false; } }", timeout=45000)
        ui = json.loads(page.locator('pre').inner_text())
        diagnostic = ui.get('cookie_path_diagnostics', {})
        issuer_names = {item['name'] for item in requests.values() if item['path'] == ISSUE and not item['redirected']}
        name = next(iter(issuer_names)) if len(issuer_names) == 1 else None
        for _ in range(100):
            relevant = {key: value for key, value in requests.items() if value['name'] == name}
            if (len(relevant) == 4 and all(key in extras and key in responses for key in relevant)
                    and all((name, path) in bodies for path in (ISSUE, INSIDE, OUTSIDE))):
                break
            page.wait_for_timeout(50)
        captured = bodies.get((name, ISSUE), {})
        report.update(cookie_name=name, backend_set_cookie=captured.get('backend'), vite_set_cookie=captured.get('vite'),
            ui={'browser_result': ui.get('browser_result') if ui.get('browser_result') in ('PASS', 'FAIL') else 'INVALID',
                'outside_count': ui.get('cookie_outside_name_count') if type(ui.get('cookie_outside_name_count')) is int else None,
                'outside_diagnostic_count': safe_boundary(diagnostic.get('outside')).get('backend_count')})
        for key, row in requests.items():
            if row['name'] != name:
                continue
            extra = extras.get(key, {})
            report['requests'].append({'path': row['path'], 'cookie_name': name, 'redirected': row['redirected'],
                'wire_observed': key in extras, 'response_observed': key in responses,
                'browser_count': extra.get('counts', {}).get(name, 0) if key in extras else None,
                'associated_cookies': [item for item in extra.get('associated', []) if item['name'] == name],
                'response_cookies': [item for item in responses.get(key, []) if item['name'] == name],
                'boundary': bodies.get((name, row['path']), {}) if row['path'] in (INSIDE, OUTSIDE) else {}})
        report['stored_cookies'] = [safe for cookie in context.cookies() if cookie['name'] == name
                                    if (safe := attributes(cookie)) is not None]
        report['findings'] = classify(report)
        if ui.get('commit') != commit:
            report['findings'].append('SOURCE_COMMIT_MISMATCH')
        report['result'] = 'PASS' if not report['findings'] else 'FAIL'
        context.close()
        browser.close()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if not args.output.resolve().is_relative_to(root / 'var/m00'):
        raise SystemExit('Output must be under ignored var/m00')
    try:
        report = run(args.origin, args.commit)
    except Exception as error:
        # Never emit Playwright exception text/call logs, raw protocol data or cookies.
        report = {'result': 'FAIL', 'error_type': type(error).__name__, 'findings': ['BROWSER_RUN_INCOMPLETE'], 'commit': args.commit}
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    sys.exit(0 if report['result'] == 'PASS' else 1)
