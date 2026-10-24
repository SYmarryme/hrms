"""Synthetic GET-only deployment probe. No HRMS users, sessions or business DB."""
import os
import re
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse

origin = urlsplit(os.environ['T004_PUBLIC_ORIGIN'])
if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in ('', '/'):
    raise ValueError('A bare HTTPS origin is required')
external_host = origin.hostname.lower() + (f':{origin.port}' if origin.port and origin.port != 443 else '')
commit = os.environ['T004_COMMIT']
if not re.fullmatch('[0-9a-f]{40}', commit):
    raise ValueError('Expected an actual Git commit')
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
COOKIE = 'hrms_t004_probe'


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
def cookie(response: Response):
    # Public constant diagnostic marker. It cannot authenticate anyone.
    response.set_cookie(COOKIE, 'poc-not-a-session', secure=True, httponly=True,
                        samesite='lax', path='/api/v1/poc/', max_age=600)
    return {'fixture': 'hrms-t004', 'cookie_set': True}


@app.get('/api/v1/poc/cookie-check')
@app.get('/api/v1/poc-outside/cookie-check')
def cookie_check(request: Request):
    return {'fixture': 'hrms-t004', 'received': request.cookies.get(COOKIE) == 'poc-not-a-session'}


@app.get('/api/v1/poc/browser-cookie', response_class=HTMLResponse)
def browser_cookie(request: Request):
    # A real document INSIDE the cookie Path: checking document.cookie at / would
    # hide this cookie because of Path alone and could falsely imply HttpOnly.
    received = 'true' if request.cookies.get(COOKIE) == 'poc-not-a-session' else 'false'
    return HTMLResponse('<!doctype html><html><head><title>T004 cookie context</title></head>'
                        f'<body data-t004-cookie-context data-cookie-received="{received}">'
                        'Synthetic cookie path context only.</body></html>')
