"""CloudStudio in-memory regressions; only fabricated cookies, no HTTP server."""
import http.cookiejar
import unittest
from email.message import Message
from http.cookies import SimpleCookie
from types import SimpleNamespace
from urllib.parse import urlsplit
from urllib.request import Request as ClientRequest

from starlette.requests import Request
from starlette.responses import Response

import backend

ID_A = 'a' * 32
ID_B = 'b' * 32
ORIGIN = 'https://t004-regression.invalid'
INSIDE = '/api/v1/poc/cookie-check'
OUTSIDE = '/api/v1/poc-outside/cookie-check'


def issue(jar, probe_id):
    response = Response()
    backend.cookie(response, probe_id=probe_id)
    headers = Message()
    for name, value in response.raw_headers:
        if name.lower() == b'set-cookie':
            headers.add_header('Set-Cookie', value.decode('latin-1'))
    jar.extract_cookies(SimpleNamespace(info=lambda: headers),
                        ClientRequest(ORIGIN + '/api/v1/poc/cookie?probe_id=' + probe_id))
    return headers


def server_request(jar, path):
    outgoing = ClientRequest(ORIGIN + path)
    jar.add_cookie_header(outgoing)
    return request_with_cookie(urlsplit(outgoing.full_url).path, outgoing.get_header('Cookie', ''))


def request_with_cookie(path, header):
    return Request({'type': 'http', 'method': 'GET', 'path': path, 'root_path': '',
                    'scheme': 'https', 'server': ('t004-regression.invalid', 443), 'query_string': b'',
                    'headers': [(b'host', b't004-regression.invalid'), (b'cookie', header.encode('latin-1'))]})


class CookiePathRegression(unittest.TestCase):
    def test_issued_attributes_remain_strict(self):
        headers = issue(http.cookiejar.CookieJar(), ID_A)
        parsed = SimpleCookie()
        for header in headers.get_all('Set-Cookie'):
            parsed.load(header)
        self.assertEqual(len(parsed), 1)
        marker = next(iter(parsed.values()))
        self.assertEqual(marker.key, 'hrms_t004_probe_' + ID_A)
        self.assertTrue(marker['secure'])
        self.assertTrue(marker['httponly'])
        self.assertEqual(marker['samesite'].lower(), 'lax')
        self.assertEqual(marker['path'], '/api/v1/poc/')
        self.assertFalse(marker['domain'])

    def test_clean_client_sends_current_cookie_only_inside_path(self):
        jar = http.cookiejar.CookieJar()
        issue(jar, ID_A)
        inside = backend.cookie_check(server_request(jar, INSIDE), probe_id=ID_A)
        outside = backend.cookie_check(server_request(jar, OUTSIDE), probe_id=ID_A)
        self.assertTrue(inside['received'])
        self.assertEqual(inside['cookie_name_count'], 1)
        self.assertFalse(outside['cookie_name_present'])
        self.assertEqual(outside['cookie_name_count'], 0)
        self.assertEqual(outside['observed_path'], OUTSIDE)

    def test_legacy_broad_cookie_reproduces_old_false_attribution(self):
        jar = http.cookiejar.CookieJar()
        # Deliberately bad client fixture, NEVER issued by a server endpoint.
        jar.set_cookie(http.cookiejar.Cookie(
            version=0, name='hrms_t004_probe', value='poc-not-a-session', port=None,
            port_specified=False, domain='t004-regression.invalid', domain_specified=False,
            domain_initial_dot=False, path='/', path_specified=True, secure=True,
            expires=None, discard=True, comment=None, comment_url=None,
            rest={'HttpOnly': None, 'SameSite': 'Lax'}))
        issue(jar, ID_A)
        request = server_request(jar, OUTSIDE)
        self.assertTrue(request.cookies.get('hrms_t004_probe') == 'poc-not-a-session')
        observation = backend.cookie_check(request, probe_id=ID_A)
        self.assertTrue(observation['legacy_cookie_present'])
        self.assertFalse(observation['cookie_name_present'])
        self.assertFalse(observation['received'])

    def test_distinct_runs_do_not_reuse_cookie_identity(self):
        jar = http.cookiejar.CookieJar()
        issue(jar, ID_A)
        self.assertFalse(backend.cookie_check(server_request(jar, INSIDE), probe_id=ID_B)['received'])
        issue(jar, ID_B)
        for probe_id in (ID_A, ID_B):
            self.assertTrue(backend.cookie_check(server_request(jar, INSIDE), probe_id=probe_id)['received'])
            self.assertFalse(backend.cookie_check(server_request(jar, OUTSIDE), probe_id=probe_id)['cookie_name_present'])

    def test_duplicate_current_name_is_not_collapsed_into_success(self):
        name = 'hrms_t004_probe_' + ID_A
        request = request_with_cookie(INSIDE, f'{name}=poc-not-a-session; {name}=poc-not-a-session')
        observed = backend.cookie_check(request, probe_id=ID_A)
        self.assertEqual(observed['cookie_name_count'], 2)
        self.assertTrue(observed['cookie_name_present'])
        self.assertFalse(observed['received'])

    def test_same_name_with_wrong_value_is_still_reported_present(self):
        request = request_with_cookie(OUTSIDE, 'hrms_t004_probe_' + ID_A + '=fabricated-wrong-value')
        observed = backend.cookie_check(request, probe_id=ID_A)
        self.assertFalse(observed['received'])
        self.assertTrue(observed['cookie_name_present'])
        self.assertEqual(observed['cookie_name_count'], 1)

    def test_browser_path_document_is_bound_to_the_current_run(self):
        jar = http.cookiejar.CookieJar()
        issue(jar, ID_A)
        inside = server_request(jar, '/api/v1/poc/browser-cookie')
        self.assertIn(b'data-cookie-received="true"', backend.browser_cookie(inside, probe_id=ID_A).body)
        self.assertIn(b'data-cookie-received="false"', backend.browser_cookie(inside, probe_id=ID_B).body)


if __name__ == '__main__':
    unittest.main()
