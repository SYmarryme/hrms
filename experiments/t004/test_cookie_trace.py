"""Pure synthetic classifier checks, separate from the retained seven cookie tests."""
import unittest

from t004_browser import BASE, FRAME, INSIDE, ISSUE, OUTSIDE, classify, name_counts, set_cookie_attributes

NAME = 'hrms_t004_probe_' + 'a' * 32
ATTRS = {'name': NAME, 'path': BASE, 'secure': True, 'httpOnly': True, 'sameSite': 'lax', 'domain_present': False}


def healthy():
    rows = []
    for path in (ISSUE, INSIDE, OUTSIDE, FRAME):
        count = 1 if path in (INSIDE, FRAME) else 0
        rows.append({'path': path, 'cookie_name': NAME, 'wire_observed': True, 'response_observed': True,
            'browser_count': count, 'associated_cookies': [{**ATTRS, 'blocked': False}] if count else [],
            'response_cookies': [ATTRS.copy()] if path == ISSUE else [],
            'boundary': {'cookie_name': NAME, 'backend_path': path, 'backend_count': count,
                'proxy': {'ingress_path': path, 'outgoing_path': path, 'ingress_count': count, 'outgoing_count': count}}})
    return {'cookie_name': NAME, 'backend_set_cookie': ATTRS.copy(), 'vite_set_cookie': ATTRS.copy(),
            'stored_cookies': [ATTRS.copy()], 'requests': rows,
            'ui': {'outside_count': 0, 'outside_diagnostic_count': 0, 'browser_result': 'PASS'}}


class CookieTraceRegression(unittest.TestCase):
    def test_complete_healthy_chain(self):
        self.assertEqual(classify(healthy()), [])

    def test_edge_response_path_rewrite_is_distinguished(self):
        report = healthy()
        report['requests'][0]['response_cookies'][0]['path'] = '/'
        # Avoid mutation aliasing so the backend/vite evidence stays strict.
        self.assertIn('EDGE_SET_COOKIE_TRANSFORM', classify(report))

    def test_browser_real_send_outside_strict_scope_is_not_hidden(self):
        report = healthy()
        row = report['requests'][2]
        row['browser_count'] = 1
        row['associated_cookies'] = [{**ATTRS, 'blocked': False}]
        self.assertIn('BROWSER_SENT_STRICT_PATH_COOKIE_OUTSIDE_PATH', classify(report))

    def test_proxy_addition_after_browser_is_distinguished(self):
        report = healthy()
        report['requests'][2]['boundary']['proxy'].update(ingress_count=1, outgoing_count=1)
        report['requests'][2]['boundary']['backend_count'] = 1
        report['ui'].update(outside_count=1, outside_diagnostic_count=1, browser_result='FAIL')
        findings = classify(report)
        self.assertIn('EDGE_REQUEST_COOKIE_TRANSFORM', findings)
        self.assertNotIn('BROWSER_SENT_STRICT_PATH_COOKIE_OUTSIDE_PATH', findings)

    def test_frontend_miscalculation_is_distinguished(self):
        report = healthy()
        report['ui'].update(outside_count=1, outside_diagnostic_count=1, browser_result='FAIL')
        self.assertIn('FRONTEND_COUNTER_MISMATCH', classify(report))

    def test_missing_wire_data_can_never_pass(self):
        report = healthy()
        report['requests'][2].update(wire_observed=False, browser_count=None)
        self.assertIn('INCOMPLETE_OR_REDIRECTED_WIRE_EVIDENCE', classify(report))
        report = healthy()
        report['requests'][3]['redirected'] = True
        self.assertIn('INCOMPLETE_OR_REDIRECTED_WIRE_EVIDENCE', classify(report))

    def test_proxy_path_conversion_is_distinguished(self):
        report = healthy()
        report['requests'][2]['boundary']['proxy']['ingress_path'] = INSIDE
        self.assertIn('EDGE_REQUEST_PATH_TRANSFORM', classify(report))

    def test_cookie_values_are_removed_from_header_projection(self):
        fake = NAME + '=fabricated-test-value; Path=' + BASE + '; Secure; HttpOnly; SameSite=Lax'
        parsed = set_cookie_attributes(fake)
        self.assertEqual(parsed, [ATTRS])
        self.assertNotIn('fabricated-test-value', repr(parsed))
        self.assertEqual(name_counts(NAME + '=fabricated-test-value; unrelated=not-recorded'), {NAME: 1})
        missing_path = set_cookie_attributes(NAME + '=fabricated-test-value; Secure; HttpOnly; SameSite=Lax')
        self.assertEqual(missing_path[0]['path'], '')


if __name__ == '__main__':
    unittest.main()
