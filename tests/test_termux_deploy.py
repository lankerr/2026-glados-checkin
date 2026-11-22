"""Termux 安卓部署的离线合成测试：通知摘要纯函数 + 脚本关键防线。

不依赖设备、Termux 或网络；termux-notification 在测试环境必然缺失，
正好覆盖“未装 termux-api 时的降级路径”。
"""
import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "termux"))

import notify  # noqa: E402


class SummarizeTests(unittest.TestCase):
    def test_success_output_maps_to_success_title(self):
        text = "🚀 2026 GLaDOS Checkin Starting...\n✅ Server酱 推送成功"
        self.assertEqual(notify.summarize(text, 0)["title"], notify.TITLE_SUCCESS)

    def test_skip_marker_also_counts_as_finished(self):
        self.assertEqual(notify.summarize("⏭️ 自动兑换未启用", 0)["title"], notify.TITLE_SUCCESS)

    def test_any_failure_marker_wins_over_success(self):
        text = "✅ Server酱 推送成功\n❌ 签到需要人机验证，停止自动重试"
        summary = notify.summarize(text, 0)
        self.assertEqual(summary["title"], notify.TITLE_FAILURE)
        self.assertIn("人机验证", summary["body"])

    def test_plain_output_with_zero_exit_is_unknown(self):
        self.assertEqual(notify.summarize("plain log line", 0)["title"], notify.TITLE_UNKNOWN)

    def test_plain_output_with_nonzero_exit_is_failure(self):
        self.assertEqual(notify.summarize("plain log line", 3)["title"], notify.TITLE_FAILURE)

    def test_empty_output_never_crashes(self):
        summary = notify.summarize("", 0)
        self.assertEqual(summary["body"], "")
        self.assertEqual(summary["title"], notify.TITLE_UNKNOWN)

    def test_body_keeps_only_tail_lines_and_strips_blanks(self):
        lines = [f"line {i}" for i in range(20)]
        body = notify.summarize("\n\n".join(lines) + "\n\n", 0)["body"]
        kept = body.splitlines()
        self.assertEqual(len(kept), notify.MAX_BODY_LINES)
        self.assertEqual(kept[-1], "line 19")

    def test_overlong_single_line_is_clipped(self):
        line = "x" * 500
        clipped = notify.summarize(line, 0)["body"]
        self.assertLessEqual(len(clipped), notify.MAX_LINE_CHARS)
        self.assertTrue(clipped.endswith("…"))


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
        self.assertIn(notify.TITLE_SUCCESS, out)
        self.assertIn("未检测到 termux-notification", out)


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
    def test_notify_module_stays_importable_offline(self):
        # CI 上没有 Termux：模块导入与纯函数不应触碰任何设备 API
        with mock.patch.dict(os.environ, {"PATH": "/nonexistent"}):
            self.assertTrue(callable(notify.summarize))

    def test_notify_cli_runs_offline_via_subprocess(self):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "termux" / "notify.py"), "--code", "0", "✅ ok"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn(notify.TITLE_SUCCESS, proc.stdout)


if __name__ == "__main__":
    unittest.main()
