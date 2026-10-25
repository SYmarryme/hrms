"""CloudStudio-only ASGI regressions with runtime-generated synthetic tokens.

No HTTP client dependency, external network, cookies or token output.
"""
import asyncio
import hashlib
import json
import secrets
import unittest
from unittest.mock import patch

import backend

BASE = '/api/v1/poc/bearer-probes'


async def request(method, path, payload=None, authorization=()):
    body = json.dumps(payload).encode() if payload is not None else b''
    headers = [(b'host', b't004-regression.invalid'), (b'content-type', b'application/json')]
    headers.extend((b'authorization', value.encode()) for value in authorization)
    scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
             'http_version': '1.1', 'method': method, 'scheme': 'https', 'path': path,
             'raw_path': path.encode(), 'query_string': b'', 'root_path': '',
             'server': ('t004-regression.invalid', 443), 'client': ('127.0.0.1', 1234),
             'headers': headers}
    sent = False
    messages = []

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {'type': 'http.request', 'body': body, 'more_body': False}
        await asyncio.Event().wait()

    async def send(message):
        messages.append(message)

    await backend.app(scope, receive, send)
    start = next(message for message in messages if message['type'] == 'http.response.start')
    raw = b''.join(message.get('body', b'') for message in messages if message['type'] == 'http.response.body')
    return start['status'], json.loads(raw), start['headers'], raw


class BearerRegression(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.token = secrets.token_hex(32)
        digest = hashlib.sha256(self.token.encode()).hexdigest()
        status, data, _, raw = await request('POST', BASE, {'token_sha256': digest})
        self.assertEqual(status, 201)
        self.assertEqual(data.get('fixture'), 'hrms-t004-bearer')
        self.assertTrue(self.token.encode() not in raw, 'Token must not appear in responses')
        self.path = BASE + '/' + data['probe_id']

    async def check(self, authorization, expected, active=True):
        status, data, headers, raw = await request('GET', self.path, authorization=authorization)
        self.assertEqual(status, expected)
        self.assertEqual(data.get('fixture'), 'hrms-t004-bearer')
        self.assertEqual(data.get('authenticated'), expected == 200)
        self.assertEqual(data.get('context_active'), active)
        self.assertTrue(self.token.encode() not in raw, 'Token must not appear in responses')
        self.assertTrue(not any(name.lower() == b'set-cookie' for name, _ in headers), 'Bearer fixture must not set cookies')
        if expected == 401:
            self.assertTrue((b'www-authenticate', b'Bearer') in headers, 'Bearer challenge required')

    async def test_correct_returns_200(self):
        await self.check(('Bearer ' + self.token,), 200)

    async def test_missing_returns_401(self):
        await self.check((), 401)

    async def test_wrong_returns_401(self):
        await self.check(('Bearer ' + secrets.token_hex(33),), 401)

    async def test_context_id_alone_or_unknown_context_cannot_authenticate(self):
        self.path = BASE + '/' + secrets.token_hex(16)
        await self.check(('Bearer ' + self.token,), 401, active=False)

    async def test_empty_other_scheme_and_duplicate_credentials_rejected(self):
        cases = [('Bearer ',), ('Basic ' + self.token,), ('Bearer ' + self.token, 'Bearer ' + self.token)]
        for credentials in cases:
            await self.check(credentials, 401)

    async def test_expired_context_returns_401(self):
        future = backend.monotonic() + backend.BEARER_TTL + 1
        with patch.object(backend, 'monotonic', return_value=future):
            await self.check(('Bearer ' + self.token,), 401, active=False)

    async def test_invalid_setup_does_not_reflect_arbitrary_input(self):
        for payload in ({'token_sha256': self.token + self.token}, {'unexpected': self.token}, {'token_sha256': self.token * 8}):
            status, _, _, raw = await request('POST', BASE, payload)
            self.assertIn(status, (400, 413))
            self.assertTrue(self.token.encode() not in raw, 'Invalid setup must not echo input')


if __name__ == '__main__':
    unittest.main()
