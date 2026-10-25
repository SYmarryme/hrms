"""Synthetic GET-only deployment probe. No HRMS users, sessions or business DB."""
import os
import re
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import HTMLResponse

origin = urlsplit(os.environ['T004_PUBLIC_ORIGIN'])
if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in ('', '/'):
    raise ValueError('A bare HTTPS origin is required')
external_host = origin.hostname.lower() + (f':{origin.port}' if origin.port and origin.port != 443 else '')
commit = os.environ['T004_COMMIT']
if not re.fullmatch('[0-9a-f]{40}', commit):
    raise ValueError('Expected an actual Git commit')
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
LEGACY_COOKIE = 'hrms_t004_probe'
COOKIE_PREFIX = LEGACY_COOKIE + '_'
COOKIE_VALUE = 'poc-not-a-session'
COOKIE_PATH = '/api/v1/poc/'


def issued_cookie_attributes(response: Response, name: str):
    cookies = SimpleCookie()
    for header in response.headers.getlist('set-cookie'):
        cookies.load(header)
    marker = cookies[name]
    return {'name': marker.key, 'path': marker['path'], 'secure': bool(marker['secure']),
            'httpOnly': bool(marker['httponly']), 'sameSite': marker['samesite'].lower(),
            'domain_present': bool(marker['domain'])}


def proxy_observation(request: Request):
    def integer(header):
        value = request.headers.get(header, '')
        return int(value) if value.isdigit() and len(value) < 5 else None

    def path(header):
        value = request.headers.get(header, '')
        return value if value.startswith('/') and len(value) <= 512 and not any(
            char in value for char in ('?', '#', '\r', '\n', '\x00')) else None

    return {
        'ingress_path': path('x-t004-vite-in-path'),
        'outgoing_path': path('x-t004-vite-out-path'),
        'ingress_count': integer('x-t004-vite-in-count'),
        'outgoing_count': integer('x-t004-vite-out-count'),
    }


def cookie_observation(request: Request, probe_id: str):
    name = COOKIE_PREFIX + probe_id

    def count(expected_name):
        return sum(part.partition('=')[0].strip() == expected_name
                   for header in request.headers.getlist('cookie') for part in header.split(';'))

    occurrences = count(name)
    return {
        'fixture': 'hrms-t004', 'observed_path': request.url.path,
        'cookie_name': name, 'proxy': proxy_observation(request),
        'received': occurrences == 1 and request.cookies.get(name) == COOKIE_VALUE,
        'cookie_name_present': occurrences > 0, 'cookie_name_count': occurrences,
        # Observation only; old cookies are never treated as the current probe.
        'legacy_cookie_present': count(LEGACY_COOKIE) > 0,
    }


@app.middleware('http')
async def no_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.get('/api/v1/poc/health')
def health(request: Request):
    # Observations only. These headers NEVER grant identity or set cookie security.
    return {
        'fixture': 'hrms-t004', 'status': 'ok', 'commit': commit,
        'transport_scheme': request.url.scheme,
        'forwarded_proto_https': request.headers.get('x-forwarded-proto') == 'https',
        'forwarded_host_matches': request.headers.get('x-forwarded-host', '').lower() == external_host,
        'forwarded_present': 'forwarded' in request.headers,
        'forwarded_for_present': 'x-forwarded-for' in request.headers,
    }


@app.get('/api/v1/poc/cookie')
def cookie(response: Response, probe_id: str = Query(..., pattern=r'^[0-9a-f]{32}$')):
    # Public constant diagnostic marker. It cannot authenticate anyone.
    response.set_cookie(COOKIE_PREFIX + probe_id, COOKIE_VALUE, secure=True, httponly=True,
                        samesite='lax', path=COOKIE_PATH, max_age=600)
    return {'fixture': 'hrms-t004', 'cookie_set': True, 'declared_path': COOKIE_PATH,
            'run_scoped': True, 'backend_set_cookie': issued_cookie_attributes(response, COOKIE_PREFIX + probe_id)}


@app.get('/api/v1/poc/cookie-check')
@app.get('/api/v1/poc-outside/cookie-check')
def cookie_check(request: Request, probe_id: str = Query(..., pattern=r'^[0-9a-f]{32}$')):
    return cookie_observation(request, probe_id)


@app.get('/api/v1/poc/browser-cookie', response_class=HTMLResponse)
def browser_cookie(request: Request, probe_id: str = Query(..., pattern=r'^[0-9a-f]{32}$')):
    # A real document INSIDE the cookie Path: checking document.cookie at / would
    # hide this cookie because of Path alone and could falsely imply HttpOnly.
    received = 'true' if cookie_observation(request, probe_id)['received'] else 'false'
    return HTMLResponse('<!doctype html><html><head><title>T004 cookie context</title></head>'
                        f'<body data-t004-cookie-context data-cookie-received="{received}">'
                        'Synthetic cookie path context only.</body></html>')
