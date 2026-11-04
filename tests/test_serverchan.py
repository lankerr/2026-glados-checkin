import os
import unittest
from unittest import mock

import checkin


SENDKEY = 'SCT123synthetic-sendkey'
COOKIE = 'gld:sess=synthetic-session; gld:sess.sig=synthetic-signature'


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        network = mock.patch(
            'requests.sessions.Session.request',
            side_effect=AssertionError('Live HTTP disabled in notification tests'),
        )
        network.start()
        self.addCleanup(network.stop)
        logging = mock.patch('checkin.log')
        self.log = logging.start()
        self.addCleanup(logging.stop)


class ServerChanRequestTests(OfflineTestCase):
    def successful_response(self):
        response = mock.Mock()
        response.json.return_value = {'code': 0, 'data': {'pushid': 'synthetic'}}
        return response

    @mock.patch('checkin.requests.post')
    def test_missing_or_blank_key_skips_request(self, post):
        for key in (None, '', '  \n '):
            with self.subTest(key=key):
                self.assertFalse(checkin.serverchan_push(key, '签到结果', '<p>成功</p>'))
        post.assert_not_called()

    @mock.patch('checkin.requests.post')
    def test_turbo_posts_title_and_body_as_json(self, post):
        post.return_value = self.successful_response()

        self.assertTrue(checkin.serverchan_push(SENDKEY, '签到结果', '<p>成功</p>'))

        args, kwargs = post.call_args
        self.assertEqual(args, (f'https://sctapi.ftqq.com/{SENDKEY}.send',))
        self.assertEqual(kwargs['timeout'], 10)
        self.assertEqual(kwargs['json']['title'], '签到结果')
        self.assertIn('成功', kwargs['json']['desp'])
        self.assertNotIn('data', kwargs)
        post.return_value.raise_for_status.assert_called_once_with()

    @mock.patch('checkin.requests.post')
    def test_serverchan3_uses_key_specific_host(self, post):
        post.return_value = self.successful_response()
        key = 'sctp123tSyntheticSendkey'

        self.assertTrue(checkin.serverchan_push(key, '签到结果', '<p>成功</p>'))

        self.assertEqual(
            post.call_args.args[0],
            f'https://123.push.ft07.com/send/{key}.send',
        )

    @mock.patch('checkin.requests.post')
    def test_html_report_becomes_readable_markdown(self, post):
        post.return_value = self.successful_response()
        content = '''
<div style="border:2px solid #333">
    <h3>👤 first@example.test</h3>
    <p><b>当前积分:</b> <span style="color:red">500</span> (+20)</p>
    <p><b>剩余天数:</b> 99 天</p>
    <p><b>签到结果:</b> Checkin! &amp; reward</p>
    <p><b>自动兑换:</b> 兑换成功 +100天</p>
    <div><p>兑换选项:</p><p>100分→10天<br>500分→100天</p></div>
</div>
<div><h3>👤 second@example.test</h3><p>签到结果: 已签到</p></div>
<br><small>时间: 2026-11-05 09:30:00</small>
'''

        self.assertTrue(checkin.serverchan_push(SENDKEY, '签到汇总', content))

        body = post.call_args.kwargs['json']['desp']
        for text in (
            'first@example.test', 'second@example.test', '当前积分:', '500',
            '(+20)', '剩余天数:', '99 天', 'Checkin! & reward',
            '自动兑换:', '兑换成功 +100天', '兑换选项:', '100分→10天',
            '500分→100天', '已签到', '2026-11-05 09:30:00',
        ):
            self.assertIn(text, body)
        for markup in ('<div', '<p>', '<h3>', '<span', '<br>', '<small>', 'style=', '&amp;'):
            self.assertNotIn(markup, body)
        self.assertTrue('  \n' in body or '\n\n' in body)
        self.assertLess(body.index('first@example.test'), body.index('second@example.test'))

    @mock.patch('checkin.requests.post')
    def test_nonzero_or_missing_api_code_is_failure(self, post):
        for payload in ({'code': 40001}, {'code': 200}, {}, {'data': {'pushid': 'synthetic'}}):
            with self.subTest(payload=payload):
                post.return_value = mock.Mock()
                post.return_value.json.return_value = payload
                self.assertFalse(checkin.serverchan_push(SENDKEY, '签到结果', '<p>成功</p>'))

    @mock.patch('checkin.requests.post')
    def test_malformed_json_or_non_object_response_is_failure(self, post):
        for payload in (None, [], 'not an object', 0):
            with self.subTest(payload=payload):
                post.return_value = mock.Mock()
                post.return_value.json.return_value = payload
                self.assertFalse(checkin.serverchan_push(SENDKEY, '签到结果', '<p>成功</p>'))
        post.return_value.json.side_effect = ValueError('invalid JSON')
        self.assertFalse(checkin.serverchan_push(SENDKEY, '签到结果', '<p>成功</p>'))

    @mock.patch('checkin.requests.post')
    def test_http_error_is_failure_without_exposing_key(self, post):
        post.return_value.raise_for_status.side_effect = checkin.requests.HTTPError(
            f'403 Client Error for url: https://sctapi.ftqq.com/{SENDKEY}.send'
        )

        self.assertFalse(checkin.serverchan_push(SENDKEY, '签到结果', '<p>成功</p>'))

        post.return_value.json.assert_not_called()
        self.assertNotIn(SENDKEY, str(self.log.call_args_list))

    @mock.patch('checkin.requests.post')
    def test_connection_error_is_failure_without_exposing_key(self, post):
        for error_type in (checkin.requests.ConnectionError, checkin.requests.Timeout):
            with self.subTest(error=error_type):
                post.side_effect = error_type(f'Request failed: {SENDKEY}')
                self.assertFalse(checkin.serverchan_push(SENDKEY, '签到结果', '<p>成功</p>'))
        self.assertNotIn(SENDKEY, str(self.log.call_args_list))

    @mock.patch('checkin.requests.post')
    def test_api_error_does_not_echo_key_from_response(self, post):
        post.return_value.json.return_value = {'code': 40001, 'message': f'invalid key {SENDKEY}'}

        self.assertFalse(checkin.serverchan_push(SENDKEY, '签到结果', '<p>成功</p>'))

        self.assertNotIn(SENDKEY, str(self.log.call_args_list))


class ServerChanMainTests(OfflineTestCase):
    def run_main(self, environment=None, failure=False, exchange_result=None, serverchan_ok=True):
        client = mock.Mock()
        client.email = 'synthetic@example.test'
        client.points = '500'
        client.points_change = '+20'
        client.left_days = '99'
        client.exchange_info = '100分→10天<br>500分→100天'
        client.exchange_result = ''
        client.checkin.return_value = (
            {'code': -2, 'message': '没有权限'} if failure else
            {'code': 0, 'message': 'Checkin! Got 20 Points'}
        )
        client.req.return_value = {'code': 0, 'data': {'leftDays': '99'}}
        config = {
            'GLADOS_COOKIE': COOKIE,
            'SERVERCHAN_SENDKEY': SENDKEY,
            'EXCHANGE_PLAN': 'off',
            'PUSH_LEVEL': 'all',
        }
        config.update(environment or {})
        with mock.patch.dict(os.environ, config, clear=True), \
                mock.patch('checkin.GLaDOS', return_value=client), \
                mock.patch('checkin.serverchan_push', return_value=serverchan_ok) as serverchan, \
                mock.patch('checkin.pushplus') as pushplus, \
                mock.patch('checkin.telegram_push') as telegram, \
                mock.patch('checkin.auto_exchange', return_value=exchange_result) as exchange:
            exit_code = checkin.main()
        return exit_code, serverchan, pushplus, telegram, exchange, client

    def test_serverchan_only_configuration_sends_summary(self):
        exit_code, serverchan, pushplus, telegram, _, _ = self.run_main()

        self.assertEqual(exit_code, 0)
        serverchan.assert_called_once()
        key, title, body = serverchan.call_args.args
        self.assertEqual(key, SENDKEY)
        self.assertEqual(title, 'GLaDOS签到: 本次运行成功 1/1')
        self.assertIn('synthetic@example.test', body)
        self.assertIn('500', body)
        self.assertIn('99', body)
        self.assertIn('时间（北京时间 UTC+8）:', body)
        pushplus.assert_not_called()
        telegram.assert_not_called()

    def test_all_configured_channels_receive_summary(self):
        _, serverchan, pushplus, telegram, _, _ = self.run_main({
            'PUSHPLUS_TOKEN': 'synthetic-pushplus-token',
            'TELEGRAM_BOT_TOKEN': 'synthetic-telegram-token',
            'TELEGRAM_CHAT_ID': 'synthetic-chat-id',
        })

        serverchan.assert_called_once()
        pushplus.assert_called_once()
        telegram.assert_called_once()
        self.assertEqual(serverchan.call_args.args[1:], pushplus.call_args.args[1:])
        self.assertEqual(serverchan.call_args.args[1:], telegram.call_args.args[2:])

    def test_default_fail_only_skips_success_without_exchange(self):
        exit_code, serverchan, _, _, _, _ = self.run_main({'PUSH_LEVEL': 'fail_only'})

        self.assertEqual(exit_code, 0)
        serverchan.assert_not_called()

    def test_fail_only_sends_failure_and_preserves_failure_exit(self):
        exit_code, serverchan, _, _, _, _ = self.run_main(
            {'PUSH_LEVEL': 'fail_only'}, failure=True,
        )

        self.assertEqual(exit_code, 1)
        serverchan.assert_called_once()
        self.assertEqual(serverchan.call_args.args[1], 'GLaDOS签到: 本次运行失败 0/1')
        self.assertIn('今日签到状态未知', serverchan.call_args.args[2])

    def test_exchange_success_or_failure_notifies_even_in_fail_only(self):
        for result in ('🎁 兑换成功 +100天', '⚠️ 兑换失败(Network Error)'):
            with self.subTest(result=result):
                exit_code, serverchan, _, _, exchange, _ = self.run_main(
                    {'PUSH_LEVEL': 'fail_only', 'EXCHANGE_PLAN': 'plan500'},
                    exchange_result=result,
                )

                self.assertEqual(exit_code, 0)
                exchange.assert_called_once()
                serverchan.assert_called_once()
                self.assertIn(result, serverchan.call_args.args[2])

    def test_diagnostic_mode_does_not_notify_or_modify_account(self):
        exit_code, serverchan, pushplus, telegram, exchange, client = self.run_main({
            'CHECKIN_DIAGNOSTIC_ONLY': 'true',
            'PUSHPLUS_TOKEN': 'synthetic-pushplus-token',
            'TELEGRAM_BOT_TOKEN': 'synthetic-telegram-token',
            'TELEGRAM_CHAT_ID': 'synthetic-chat-id',
        })

        self.assertEqual(exit_code, 0)
        client.req.assert_called_once_with('GET', '/api/user/status')
        client.checkin.assert_not_called()
        exchange.assert_not_called()
        serverchan.assert_not_called()
        pushplus.assert_not_called()
        telegram.assert_not_called()

    def test_serverchan_failure_keeps_other_channels_and_checkin_result(self):
        exit_code, serverchan, pushplus, telegram, _, _ = self.run_main({
            'PUSHPLUS_TOKEN': 'synthetic-pushplus-token',
            'TELEGRAM_BOT_TOKEN': 'synthetic-telegram-token',
            'TELEGRAM_CHAT_ID': 'synthetic-chat-id',
        }, serverchan_ok=False)

        self.assertEqual(exit_code, 0)
        serverchan.assert_called_once()
        pushplus.assert_called_once()
        telegram.assert_called_once()


if __name__ == '__main__':
    unittest.main()
