import io
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest import mock

import update_streak


class TermuxLedgerTests(unittest.TestCase):
    def test_preview_has_no_account_access_and_returns_delivery_status(self):
        with mock.patch('checkin.get_cookies', side_effect=AssertionError('no account access')), \
                mock.patch('shutil.which', return_value='notify'), mock.patch('subprocess.run') as run:
            for code in (0, 1):
                run.return_value.returncode = code
                self.assertEqual(update_streak.test_notification(), code)
                self.assertIn('本机测试消息', run.call_args.args[0][-1])

    def test_missing_failed_or_timed_out_notification_keeps_terminal_report(self):
        cases = [(None, None), ('notify', mock.Mock(returncode=1)),
                 ('notify', subprocess.TimeoutExpired('notify', 15))]
        for binary, result in cases:
            with self.subTest(binary=binary, result=result), \
                    mock.patch('shutil.which', return_value=binary), \
                    mock.patch('subprocess.run') as run, redirect_stdout(io.StringIO()) as output:
                if isinstance(result, Exception):
                    run.side_effect = result
                else:
                    run.return_value = result
                update_streak.notify_termux(1, 2, False)
                self.assertIn('本地通知命令未成功', output.getvalue())
                self.assertIn('1/2', output.getvalue())
                self.assertEqual(run.call_count, int(bool(binary)))

    def test_partial_read_notifies_with_counts_only_and_keeps_failure_status(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch('checkin.get_cookies', return_value=['private-1', 'private-2']), \
                mock.patch('checkin.beijing_now', return_value=datetime(2026, 11, 25)), \
                mock.patch('checkin.GLaDOS') as factory, \
                mock.patch('shutil.which', return_value='notify'), \
                mock.patch('subprocess.run', return_value=mock.Mock(returncode=0)) as run, \
                redirect_stdout(io.StringIO()) as output:
            first, second = mock.Mock(), mock.Mock()
            first.get_points.return_value = False
            first.points_error = 'HTTP 403'
            second.get_points.return_value = True
            second.recent_entries = [{'business': 'checkin', 'date': '2026-11-25', 'change': '+3'}]
            factory.side_effect = [first, second]
            self.assertEqual(update_streak.main(termux_notify=True), 1)
            for client in (first, second):
                client.get_points.assert_called_once_with()
                client.checkin.assert_not_called()
                client.exchange.assert_not_called()
            args = run.call_args.args[0]
            self.assertIn('GLaDOS 流水读取异常', args)
            self.assertIn('1/2', args[-1])
            self.assertNotIn('private', str(args) + output.getvalue())
            self.assertIn('HTTP 403', output.getvalue())

    @unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'POSIX shell entry point')
    def test_shell_entry_loads_private_config_and_runs_only_the_report(self):
        script = Path(__file__).resolve().parents[1] / 'termux' / 'run-ledger.sh'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {'HOME': tmp, 'PATH': tmp + os.pathsep + os.defpath}
            fake_python = root / 'python'
            fake_python.write_text('#!/bin/sh\nprintf "%s\\n" "$@" "$GLADOS_COOKIE"\n')
            fake_python.chmod(0o700)
            configs = root / '.config/glados-termux'
            configs.mkdir(parents=True)
            (configs / 'env').write_text("GLADOS_COOKIE='fixture from default'\n")
            custom = root / 'custom-env'
            custom.write_text("GLADOS_COOKIE='fixture from override'\n")
            for options, expected in [({}, 'fixture from default'),
                                      ({'GLADOS_TERMUX_ENV': str(custom)}, 'fixture from override')]:
                result = subprocess.run(['bash', str(script)], env={**env, **options},
                                        capture_output=True, text=True, check=True)
                entry, flag, cookie = result.stdout.splitlines()
                self.assertEqual(Path(entry).resolve(), script.parents[1] / 'update_streak.py')
                self.assertEqual((flag, cookie), ('--termux-notify', expected))
            env['GLADOS_TERMUX_ENV'] = str(root / 'missing')
            result = subprocess.run(['bash', str(script)], env=env, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b'')
