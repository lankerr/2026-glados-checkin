import os
import unittest
from unittest import mock

import checkin


COOKIE = 'gld:sess=synthetic-private; gld:sess.sig=synthetic-signature'
NONCE = 'synthetic-nonce'
PROOF = '95d98116667d20076de5e31eeba57cb65dac0e9be21afb32263bac1178699533'


def response(payload, status=200):
    return mock.Mock(status_code=status, **{'json.return_value': payload})


class ChallengeTests(unittest.TestCase):
    def setUp(self):
        for patch in (
            mock.patch.dict(os.environ, {'GLADOS_USER_AGENT': 'SyntheticBrowser/1.0'}, clear=True),
            mock.patch('requests.sessions.Session.request', side_effect=AssertionError('Live HTTP disabled')),
            mock.patch('checkin.log'),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    @mock.patch('checkin.time.monotonic', side_effect=[100, 102.7])
    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_official_challenge_flow_preserves_cookie_and_waits_before_post(self, get, post, sleep, timer):
        get.return_value = response({'code': 0, 'nonce': NONCE, 'ttl': 300000})
        post.return_value = response({'code': 0, 'message': 'Checkin! Got 12 Points'})

        result = checkin.GLaDOS(COOKIE).checkin()

        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], checkin.DOMAINS[0] + '/api/user/checkin/challenge')
        sleep.assert_called_once_with(2.7)
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], checkin.DOMAINS[0] + '/api/user/checkin')
        self.assertEqual(post.call_args.kwargs['json'], {
            'token': 'glados.cloud', 'nonce': NONCE, 'proof': PROOF,
        })
        self.assertEqual(get.call_args.kwargs['headers']['Cookie'], COOKIE)
        self.assertEqual(post.call_args.kwargs['headers']['Cookie'], COOKIE)
        self.assertEqual(post.call_args.kwargs['headers']['User-Agent'], 'SyntheticBrowser/1.0')
        self.assertTrue(checkin.is_normal_checkin_result(result))

    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_challenge_fallback_binds_post_and_token_to_issuing_origin(self, get, post, sleep):
        get.side_effect = [response({}, 500), response({'code': 0, 'nonce': NONCE, 'ttl': 300000})]
        post.return_value = response({'code': 0})

        self.assertTrue(checkin.is_normal_checkin_result(checkin.GLaDOS(COOKIE).checkin()))

        self.assertEqual(post.call_args.args[0], checkin.DOMAINS[1] + '/api/user/checkin')
        self.assertEqual(post.call_args.kwargs['json']['token'], 'glados.rocks')
        self.assertEqual(post.call_args.kwargs['headers']['Origin'], checkin.DOMAINS[1])

    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_bad_challenge_never_degrades_to_token_only_checkin(self, get, post, sleep):
        for data in (
            {'code': 2, 'message': 'private error ' + COOKIE},
            {'code': 0}, {'code': 0, 'nonce': ''}, {'code': 0, 'nonce': []},
            {'code': 0, 'nonce': 'x' * 4097},
            *({'code': 0, 'nonce': NONCE, 'ttl': ttl} for ttl in (None, '300000', True, 0, 2500, float('inf'), float('nan'))),
        ):
            with self.subTest(data=data):
                get.return_value = response(data)
                result = checkin.GLaDOS(COOKIE).checkin()
                self.assertTrue(result['request_failed'])
                self.assertEqual(result['reason'], 'checkin-challenge-unavailable')
                self.assertNotIn('synthetic-private', str(result))
        post.assert_not_called()
        sleep.assert_not_called()

    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_challenge_auth_denial_stops_without_post_or_retry(self, get, post, sleep):
        for data, status in (({'code': -2}, 200), ({}, 403)):
            with self.subTest(status=status):
                get.reset_mock()
                get.return_value = response(data, status)
                result, ok = checkin.checkin_with_retry(checkin.GLaDOS(COOKIE))
                self.assertFalse(ok)
                self.assertTrue(checkin.is_non_retryable_checkin_result(result))
                get.assert_called_once()
        post.assert_not_called()
        sleep.assert_not_called()

    @mock.patch('checkin.time.monotonic', side_effect=[100, 104])
    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_expired_challenge_is_not_submitted(self, get, post, sleep, timer):
        get.return_value = response({'code': 0, 'nonce': NONCE, 'ttl': 3000})
        result = checkin.GLaDOS(COOKIE).checkin()
        self.assertEqual(result['reason'], 'checkin-challenge-expired')
        post.assert_not_called()

    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_post_failure_does_not_replay_nonce_on_other_domains(self, get, post, sleep):
        get.return_value = response({'code': 0, 'nonce': NONCE, 'ttl': 300000})
        post.return_value = response({}, 500)
        result = checkin.GLaDOS(COOKIE).checkin()
        self.assertTrue(result['request_failed'])
        post.assert_called_once()
        get.assert_called_once()

    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_transient_post_failure_obtains_fresh_nonce_for_next_attempt(self, get, post, sleep):
        get.side_effect = [
            response({'code': 0, 'nonce': NONCE, 'ttl': 300000}),
            response({'code': 0, 'nonce': 'another-nonce', 'ttl': 300000}),
        ]
        post.side_effect = [checkin.requests.ReadTimeout(COOKIE), response({'code': 0})]
        result, ok = checkin.checkin_with_retry(checkin.GLaDOS(COOKIE), attempts=2)
        self.assertTrue(ok)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(post.call_count, 2)
        sent = [call.kwargs['json'] for call in post.call_args_list]
        self.assertNotEqual(sent[0]['nonce'], sent[1]['nonce'])
        self.assertNotEqual(sent[0]['proof'], sent[1]['proof'])
        self.assertEqual(sleep.call_args_list, [mock.call(2.7), mock.call(60), mock.call(2.7)])

    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_ttl_must_cover_the_wait_including_its_margin(self, get, post, sleep):
        for ttl in (2501, 2699, 2700):
            with self.subTest(ttl=ttl):
                get.return_value = response({'code': 0, 'nonce': NONCE, 'ttl': ttl})
                result = checkin.GLaDOS(COOKIE).checkin()
                self.assertEqual(result['reason'], 'checkin-challenge-unavailable')
        sleep.assert_not_called()
        post.assert_not_called()

    @mock.patch('checkin.time.monotonic', side_effect=[0, 2.7])
    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_ttl_just_above_wait_allows_submission_before_expiry(self, get, post, sleep, timer):
        get.return_value = response({'code': 0, 'nonce': NONCE, 'ttl': 2701})
        post.return_value = response({'code': 0})

        result = checkin.GLaDOS(COOKIE).checkin()

        self.assertTrue(checkin.is_normal_checkin_result(result))
        sleep.assert_called_once_with(2.7)
        post.assert_called_once()

    @mock.patch('checkin.time.monotonic', side_effect=[0, 3])
    @mock.patch('checkin.time.sleep')
    @mock.patch('checkin.requests.post')
    @mock.patch('checkin.requests.get')
    def test_challenge_at_exact_expiry_after_wait_is_not_submitted(self, get, post, sleep, timer):
        get.return_value = response({'code': 0, 'nonce': NONCE, 'ttl': 3000})

        result = checkin.GLaDOS(COOKIE).checkin()

        self.assertEqual(result['reason'], 'checkin-challenge-expired')
        sleep.assert_called_once_with(2.7)
        post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
