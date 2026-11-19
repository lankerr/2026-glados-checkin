import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import update_streak


def row(day, business='checkin', change='+2'):
    return {'date': day, 'business': business, 'change': change}


class StreakReportTests(unittest.TestCase):
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
