"""Termux 安卓部署的离线合成测试：通知摘要纯函数 + 脚本关键防线。

不依赖设备、Termux 或网络；termux-notification 在测试环境必然缺失，
正好覆盖“未装 termux-api 时的降级路径”。
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "termux"))

import notify  # noqa: E402


class SummarizeTests(unittest.TestCase):
    stamp = "[2026-11-24 09:30:00 北京时间] "
    account = stamp + "✅ 账号 1 | 积分: 37 | 入账核验: 待核对 | 天数: 3 | 结果: sample-private"

    def test_only_account_result_lines_count(self):
        summary = notify.summarize(self.account + "\n❌ 推送渠道出错", 0)
        self.assertEqual(summary["title"], notify.TITLE_SUCCESS)
        self.assertIn("成功 1，失败 0", summary["body"])
        self.assertNotIn("sample-private", str(summary))

    def test_mixed_accounts(self):
        second = self.account.replace("✅ 账号 1", "❌ 账号 2")
        summary = notify.summarize(self.account + "\n" + second, 1)
        self.assertEqual(summary["title"], notify.TITLE_FAILURE)
        self.assertIn("成功 1，失败 1", summary["body"])

    def test_nonzero_exit_does_not_claim_a_completed_run(self):
        self.assertEqual(notify.summarize(self.account, 1)["title"], notify.TITLE_ERROR)
        self.assertEqual(notify.summarize("", 2)["title"], notify.TITLE_ERROR)

    def test_readonly_diagnostics_push_and_skip_are_not_checkin_results(self):
        for log in ("✅ Server酱 推送成功", "⏭️ 自动兑换未启用", "",
                    self.stamp + "✅ 账号 1: 登录状态查询成功",
                    self.account.replace("入账核验:", "流水观察:").replace("结果:", "模式:")):
            with self.subTest(log=log):
                self.assertEqual(notify.summarize(log, 0)["title"], notify.TITLE_UNKNOWN)


class LocalNotificationTests(unittest.TestCase):
    def test_degrades_to_false_without_termux_notification(self):
        with mock.patch.object(notify.shutil, "which", return_value=None):
            self.assertFalse(notify.send_local_notification({"title": "t", "body": "b"}))

    def test_main_prints_summary_and_fallback_notice(self):
        buffer = io.StringIO()
        with mock.patch.object(notify.shutil, "which", return_value=None):
            with redirect_stdout(buffer):
                code = notify.main(["--code", "0", "✅ Server酱 推送成功"])
        self.assertEqual(code, 0)
        out = buffer.getvalue()
        self.assertIn(notify.TITLE_UNKNOWN, out)
        self.assertIn("本地通知命令未成功", out)

    @mock.patch.object(notify.shutil, "which", return_value="/fake/termux-notification")
    def test_notification_command_result(self, which):
        summary = {"title": "t", "body": "b"}
        with mock.patch.object(notify.subprocess, "run") as run:
            for code in (0, 1):
                run.return_value.returncode = code
                self.assertEqual(notify.send_local_notification(summary), code == 0)
            for error in (OSError(), subprocess.TimeoutExpired("fake", 15)):
                run.side_effect = error
                self.assertFalse(notify.send_local_notification(summary))


class ScriptGuardTests(unittest.TestCase):
    """内容级防线：防止脚本漂移后悄悄失去关键保护。"""

    def setUp(self):
        self.run_script = (REPO_ROOT / "termux" / "run-checkin.sh").read_text(encoding="utf-8")
        self.bootstrap = (REPO_ROOT / "termux" / "bootstrap.sh").read_text(encoding="utf-8")

    def test_run_script_disables_browser_fallback(self):
        self.assertIn("GLADOS_BROWSER_CHECKIN=0", self.run_script)

    def test_run_script_sources_env_file_before_running_engine(self):
        self.assertLess(self.run_script.index(". \"$ENV_FILE\""), self.run_script.index("python \"$ENGINE\""))

    def test_bootstrap_never_overwrites_existing_env(self):
        self.assertIn('if [ ! -f "$ENV_FILE" ]', self.bootstrap)
        self.assertIn("chmod 600", self.bootstrap)

    def test_bootstrap_registers_persisted_job_with_network(self):
        self.assertIn("--persisted true", self.bootstrap)
        self.assertIn("--network any", self.bootstrap)
        self.assertIn("termux-wake-lock", self.bootstrap)

    def test_env_template_warns_not_to_commit_secrets(self):
        self.assertIn("不要提交", self.bootstrap)


class EngineImportTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "requires bash")
    def test_runner_preserves_exit_and_keeps_long_engine_log_out_of_notification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "termux"
            scripts.mkdir()
            for name in ("run-checkin.sh", "notify.py"):
                shutil.copyfile(REPO_ROOT / "termux" / name, scripts / name)
            (root / "env").touch()
            (root / "checkin.py").write_text("print('sample-private' * 15000)\nraise SystemExit(3)\n")
            (root / "python").symlink_to(sys.executable)
            notification = root / "termux-notification"
            notification.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CAPTURE"\nexit 1\n')
            notification.chmod(0o700)
            capture = root / "sent"
            env = {"PATH": tmp + os.pathsep + os.defpath, "HOME": tmp, "LANG": "C.UTF-8",
                   "GLADOS_TERMUX_ENV": str(root / "env"), "CAPTURE": str(capture)}
            proc = subprocess.run(["bash", str(scripts / "run-checkin.sh")], env=env,
                                  capture_output=True, encoding="utf-8", timeout=15)
            self.assertEqual(proc.returncode, 3)
            self.assertIn("本地通知命令未成功", proc.stdout)
            self.assertIn(notify.TITLE_ERROR, capture.read_text(encoding="utf-8"))
            self.assertNotIn("sample-private", capture.read_text(encoding="utf-8"))

    def test_notify_module_stays_importable_offline(self):
        # CI 上没有 Termux：模块导入与纯函数不应触碰任何设备 API
        with mock.patch.dict(os.environ, {"PATH": "/nonexistent"}):
            self.assertTrue(callable(notify.summarize))

    def test_notify_cli_runs_offline_via_subprocess(self):
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(REPO_ROOT / "termux" / "notify.py"), "--code", "0"],
            input="✅ sample-private", capture_output=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn(notify.TITLE_UNKNOWN, proc.stdout)
        self.assertNotIn("sample-private", proc.stdout)


if __name__ == "__main__":
    unittest.main()
