import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import update_streak


def row(day, business='checkin', change='+2'):
    return {'date': day, 'business': business, 'change': change}


class StreakReportTests(unittest.TestCase):
    def run_report(self, env, responses):
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / 'summary'
            with mock.patch.dict(os.environ, dict(env, GITHUB_STEP_SUMMARY=str(summary)), clear=True), \
                    mock.patch('checkin.requests.get', side_effect=responses) as get, \
                    mock.patch('checkin.requests.post', side_effect=AssertionError('expected GET only')), \
                    redirect_stdout(io.StringIO()) as output:
                status = update_streak.main()
            return status, summary.read_text(encoding='utf-8'), output.getvalue(), get.call_args_list

    def test_cookie_editor_export_is_sent_as_a_single_valid_header(self):
        raw = json.dumps([{'name': 'gld:sess', 'value': 'private&sample'},
                          {'name': 'gld:sess.sig', 'value': 'private-signature'}], indent=2)
        response = mock.Mock(status_code=200)
        response.json.return_value = {'points': 0, 'history': []}
        status, summary, log, calls = self.run_report({'GLADOS_COOKIE': raw}, [response])
        self.assertEqual(status, 0)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].args[0].endswith('/api/user/points'))
        self.assertEqual(calls[0].kwargs['headers']['Cookie'],
                         'gld:sess=private&sample; gld:sess.sig=private-signature')
        self.assertIn('无明确签到入账', summary)
        self.assertNotIn('private', summary + log)

    def test_rejected_account_does_not_hide_next_accounts_report(self):
        first = 'gld:sess=private-first; gld:sess.sig=private-sig1'
        second = 'gld:sess=private-second; gld:sess.sig=private-sig2'
        response = mock.Mock(status_code=200)
        response.json.return_value = {'points': '3', 'history': []}
        for separator in ('\n', '&'):
            with self.subTest(separator=separator):
                raw = separator.join([first, second])
                status, summary, log, calls = self.run_report(
                    {'GLADOS_COOKIE': raw}, [mock.Mock(status_code=403), response])
                self.assertEqual(status, 1)
                self.assertEqual([c.kwargs['headers']['Cookie'] for c in calls], [first, second])
                self.assertIn('账号 1：❌ 积分流水读取失败：HTTP 403', summary)
                self.assertIn('账号 2：前 10 条可见流水中无明确签到入账', summary)
                self.assertNotIn('private', summary + log)

    def test_invalid_configuration_does_not_issue_requests(self):
        for env in ({}, {'GLADOS_COOKIE': '[private-bad-json'},
                    {'GLADOS_COOKIE': 'private', 'GLADOS_USER_AGENT': 'bad\nprivate'}):
            with self.subTest(keys=list(env)):
                status, summary, log, calls = self.run_report(env, [])
                self.assertEqual(status, 1)
                self.assertIn('❌', summary)
                self.assertEqual(calls, [])
                self.assertNotIn('private', summary + log)

    def test_failed_points_reads_only_report_fixed_diagnostics(self):
        cases = [
            ({'http_status': 401}, 'HTTP 401'), ({'http_status': 503}, 'HTTP 503'),
            ({'request_failed': True, 'timed_out': True}, '超时'),
            ({'request_failed': True, 'invalid_headers': True}, '请求头'),
            ({'request_failed': True, 'invalid_response': True}, 'JSON'),
            ({'request_failed': True}, '网络'), ({'points': None}, '余额'),
            ({'points': 3, 'code': -2, 'message': 'private-echo'}, 'code=-2'),
            ({'code': 'private-code'}, '接口返回错误'),
        ]
        for payload, label in cases:
            with self.subTest(label=label), mock.patch('checkin.GLaDOS.req', return_value=payload):
                status, summary, log, _ = self.run_report({'GLADOS_COOKIE': 'private-cookie'}, [])
                self.assertEqual(status, 1)
                self.assertIn(label, summary)
                self.assertNotIn('private', summary + log)

    def test_compensation_does_not_fill_a_missing_checkin_day(self):
        entries = [
            row('2026-11-19', 'system:checkin'), row('2026-11-19', change='+0.5'),
            row('2026-11-18', 'system:compensation'), row('2026-11-17'),
        ]
        self.assertEqual(update_streak.visible_streak(entries, date(2026, 11, 19)),
                         (1, date(2026, 11, 19)))

    def test_no_positive_checkin_returns_unknown(self):
        entries = [row('2026-11-19', change='+0'), row('2026-11-19', ''),
                   row('2026-11-20'), row('invalid')]
        self.assertEqual(update_streak.visible_streak(entries, date(2026, 11, 19)),
                         (0, None))

    def test_summary_uses_latest_observed_date_and_exposes_no_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / 'summary'
            with mock.patch.dict(os.environ, {
                'GLADOS_COOKIE': 'synthetic-private-cookie',
                'GITHUB_STEP_SUMMARY': str(summary),
            }, clear=True), mock.patch('update_streak.checkin.GLaDOS') as client, \
                    mock.patch('update_streak.checkin.beijing_now', return_value=datetime(2026, 11, 19)):
                client.return_value.get_points.return_value = True
                client.return_value.recent_entries = [
                    row('2026-11-19', 'promo'), row('2026-11-18', 'check_in'),
                    row('2026-11-17', 'check-in'),
                ]
                self.assertEqual(update_streak.main(), 0)
                client.return_value.get_points.assert_called_once_with()
                client.return_value.checkin.assert_not_called()
            report = summary.read_text(encoding='utf-8')
            self.assertIn('最近可见签到为 2026-11-18', report)
            self.assertIn('连续 2 天', report)
            self.assertIn('今日签到入账仍待确认', report)
            self.assertNotIn('synthetic-private-cookie', report)
