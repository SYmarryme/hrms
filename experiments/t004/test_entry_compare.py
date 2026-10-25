"""Synthetic classification tests; no real cookies or network connections."""
import unittest

from compare_t004_entry import compare

NAME = 'hrms_t004_probe_' + 'a' * 32
ATTRS = {'name': NAME, 'path': '/api/v1/poc/', 'secure': True, 'httpOnly': True,
         'sameSite': 'lax', 'domain_present': False}


def sample():
    return {'fixture_matches': True, 'service_commit_matches': True,
            'backend': ATTRS.copy(), 'vite_metadata': ATTRS.copy(), 'received': [ATTRS.copy()]}


class EntryCompareTests(unittest.TestCase):
    def test_match_is_not_formal_acceptance(self):
        result = compare(sample(), sample(), NAME)
        self.assertEqual(result['result'], 'ATTRIBUTES_MATCH_FOR_THIS_CLIENT')
        self.assertEqual(result['formal_acceptance'], 'NOT_GRANTED')

    def test_reported_path_and_samesite_transform_blocks_current_entry(self):
        remote = sample()
        remote['received'][0].update(path='/', sameSite='none')
        result = compare(sample(), remote, NAME)
        self.assertEqual(result['result'], 'BLOCKED_CURRENT_PUBLIC_ENTRY')
        self.assertEqual(result['boundary'], 'AFTER_LOOPBACK_VITE')
        self.assertEqual(result['platform_globally_unsupported'], 'NOT_ESTABLISHED')

    def test_local_fault_is_not_assigned_to_public_platform(self):
        local = sample()
        local['received'][0]['path'] = '/'
        self.assertEqual(compare(local, sample(), NAME)['boundary'], 'LOCAL_APP_OR_VITE_CHAIN')

    def test_network_error_is_incomplete_not_proof_of_rewriting(self):
        self.assertEqual(compare(sample(), {'error_type': 'HTTPError'}, NAME)['result'], 'INCOMPLETE')

    def test_other_service_commit_cannot_establish_boundary(self):
        other = sample()
        other['service_commit_matches'] = False
        self.assertEqual(compare(sample(), other, NAME)['result'], 'INCOMPLETE')

    def test_duplicate_public_set_cookie_does_not_count_as_match(self):
        remote = sample()
        remote['received'].append(ATTRS.copy())
        self.assertEqual(compare(sample(), remote, NAME)['result'], 'INCOMPLETE')

    def test_missing_vite_metadata_cannot_establish_the_boundary(self):
        for key in ('local', 'public'):
            local, public = sample(), sample()
            (local if key == 'local' else public)['vite_metadata'] = None
            result = compare(local, public, NAME)
            self.assertEqual(result['result'], 'INCOMPLETE')
            self.assertEqual(result['boundary'], 'MISSING_VITE_METADATA')

    def test_public_vite_difference_is_not_assigned_downstream(self):
        public = sample()
        public['vite_metadata']['path'] = '/'
        public['received'][0]['path'] = '/'
        result = compare(sample(), public, NAME)
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(result['boundary'], 'PUBLIC_APP_OR_VITE_CHAIN')


if __name__ == '__main__':
    unittest.main()
