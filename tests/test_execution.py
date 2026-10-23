import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from execution_history import HistoryStore, LogPolicy
from execution_service import ExecutionService
from process_lifecycle import ProcessTree


class Terminal(QObject):
    output = Signal(str)

    def __init__(self):
        super().__init__()
        self.text = ""
        self.output.connect(self.append)

    def append(self, text):
        self.text += text

    def write_safe(self, text, color):
        self.output.emit(text)


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.history = HistoryStore(self.root / "history.db")
        self.terminal = Terminal()
        self.service = ExecutionService(self.terminal, lambda: sys.executable, history=self.history)
        self.results = []
        self.service.finished.connect(self.results.append)

    def tearDown(self):
        if self.service.busy:
            self.service.cancel()
            self.wait(lambda: not self.service.busy)
        self.service.profile_lock.unlock()
        self.tmp.cleanup()

    def wait(self, condition, timeout=8000):
        end = time.monotonic() + timeout / 1000
        while not condition() and time.monotonic() < end:
            QTest.qWait(10)
        self.assertTrue(condition())

    def activity(self, content="print('hello')", key="safe"):
        script = self.root / f"{key}.py"
        script.write_text(content, encoding="utf-8")
        return SimpleNamespace(activity_id=key, title=key, script=script)

    def run_activity(self, activity):
        self.assertTrue(self.service.start(activity))
        self.wait(lambda: not self.service.busy)
        return self.history.detail(self.results[-1]["id"])

    def test_success_failure_launch_exception_missing_and_logs(self):
        self.history.settings["log_mode"] = "redacted"
        (self.root / ".env").write_text("CLIENT_SECRET=private-profile-value\n")
        with patch.dict(os.environ, {"TEST_SECRET": "example-private-value"}):
            row = self.run_activity(self.activity("print('hello'); print('example-private-value'); print('token=private123'); print('private-profile-value')"))
        self.assertEqual(row["outcome"], "completato")
        self.assertEqual(row["exit_code"], 0)
        self.assertGreater(row["duration"], 0)
        self.assertIn("hello", row["log"])
        self.assertNotIn("example-private-value", row["log"])
        self.assertNotIn("private123", row["log"])
        self.assertNotIn("private-profile-value", row["log"])
        row = self.run_activity(self.activity("raise SystemExit(4)"))
        self.assertEqual((row["outcome"], row["exit_code"]), ("errore", 4))
        with patch.object(ProcessTree, "launch", side_effect=OSError("secret not logged")):
            row = self.run_activity(self.activity())
        self.assertEqual(row["outcome"], "errore")
        self.assertNotIn("secret not logged", row["log"])
        activity = self.activity()
        activity.script.unlink()
        self.assertEqual(self.run_activity(activity)["outcome"], "errore")

    def test_summary_minimizes_data_and_output_validation(self):
        activity = self.activity("print('confidential file row')")
        activity.output_validator = lambda: (False, "Expected output missing")
        row = self.run_activity(activity)
        self.assertEqual(row["exit_code"], 0)
        self.assertEqual(row["outcome"], "errore")
        self.assertNotIn("confidential", row["log"])
        self.assertIn("confidential", self.terminal.text)

    def test_cancellation_tree_and_concurrent_start(self):
        import psutil
        pidfile = self.root / "child.pid"
        content = ("import subprocess,sys,time,pathlib\n"
                   "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
                   f"pathlib.Path({str(pidfile)!r}).write_text(str(p.pid))\n"
                   "print('ready',flush=True)\ntime.sleep(60)\n")
        activity = self.activity(content)
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            self.assertTrue(self.service.start(activity))
            self.assertFalse(self.service.start(activity))
            self.wait(lambda: pidfile.exists() and bool(pidfile.read_text()))
            child_pid = int(pidfile.read_text())
            competing = ExecutionService(self.terminal, lambda: sys.executable, history=self.history)
            self.assertFalse(competing.start(activity))
            self.assertEqual(self.history.rows()[0]["outcome"], "in_esecuzione")
            self.service.cancel()
            self.wait(lambda: not self.service.busy)
            self.assertEqual(self.results[-1]["outcome"], "interrotto")
            self.wait(lambda: not psutil.pid_exists(child_pid))
            self.assertIsNone(unrelated.poll())
        finally:
            unrelated.terminate()
            unrelated.wait()

    def test_unreadable_secret_file_does_not_leave_execution_locked(self):
        (self.root / ".env").write_bytes(b"\xff\xfe\x00")
        self.assertEqual(self.run_activity(self.activity())["outcome"], "completato")

    def test_recovery_filters_clear_and_retention(self):
        activity = self.activity()
        run_id = self.history.start(activity, "workflow-1", 0)
        self.history.recover()
        self.assertEqual(self.history.detail(run_id)["outcome"], "interrotto")
        self.assertIsNone(self.history.detail(run_id)["duration"])
        self.assertIsNone(self.history.detail(run_id)["ended_at"])
        self.run_activity(activity)
        self.assertEqual(len(self.history.rows("safe", "completato")), 1)
        self.assertEqual(sum(self.history.statistics()["counts"].values()), 2)
        with self.history.connect() as db:
            db.execute("UPDATE runs SET started_at='2000-01-01T00:00:00+00:00' WHERE id=?", (run_id,))
        self.history.prune()
        self.assertIsNone(self.history.detail(run_id))
        self.history.clear()
        self.assertEqual(self.history.rows(), [])
