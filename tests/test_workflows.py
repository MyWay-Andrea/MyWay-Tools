import json
from dataclasses import replace
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from execution_history import HistoryStore
from execution_service import ExecutionService
from workflow_service import WorkflowManager, WorkflowStore
from activity_status import StatusService
from menu import ActivitySpec
from test_execution import Terminal
from test_status import FakeRemote


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.terminal = Terminal()
        self.activities = []
        for index in (1, 2):
            script = self.root / f"safe{index}.py"
            script.write_text(f"print('STEP_{index}',flush=True)")
            self.activities.append(ActivitySpec(index, f"Safe {index}", "", "Business", script,
                                                self.terminal, activity_id=f"safe{index}"))
        self.history = HistoryStore(self.root / "history.db")
        self.execution = ExecutionService(self.terminal, lambda: sys.executable, self.activities, self.history)
        self.status = StatusService(self.activities, FakeRemote())
        self.execution.status_service = self.status
        self.manager = WorkflowManager(self.execution, self.activities)
        self.definition = {"id": "test", "name": "Test innocuo", "steps": ["safe1", "safe2"]}
        self.wait(lambda: not self.status.scanning)

    def tearDown(self):
        if self.manager.active:
            self.manager.cancel()
            self.wait(lambda: not self.manager.active)
        if self.execution.busy:
            self.execution.cancel()
            self.wait(lambda: not self.execution.busy)
        self.status.fallback.stop()
        self.status.debounce.stop()
        self.wait(lambda: not self.status.scanning)
        self.tmp.cleanup()

    def wait(self, condition, timeout=12000):
        end = time.monotonic() + timeout / 1000
        while not condition() and time.monotonic() < end:
            QTest.qWait(10)
        self.assertTrue(condition())

    def run_workflow(self):
        self.assertTrue(self.manager.start(self.definition))
        self.wait(lambda: not self.manager.active)
        return sorted(self.history.rows(), key=lambda row: row["step_index"])

    def test_two_successful_steps_and_logs(self):
        rows = self.run_workflow()
        self.assertEqual(self.manager.outcome, "completato")
        self.assertEqual([row["activity_id"] for row in rows], ["safe1", "safe2"])
        self.assertLessEqual(rows[0]["ended_at"], rows[1]["started_at"])
        self.assertEqual(len({row["workflow_run_id"] for row in rows}), 1)
        self.assertIn("STEP_1", self.terminal.text)
        self.assertIn("STEP_2", self.terminal.text)
        self.assertEqual(self.history.workflows()[0]["outcome"], "completato")

    def test_first_failure_stops_chain(self):
        self.activities[0].script.write_text("raise SystemExit(5)")
        rows = self.run_workflow()
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.manager.outcome, "errore")
        self.assertNotIn("STEP_2", self.terminal.text)

    def test_second_failure(self):
        self.activities[1].script.write_text("raise SystemExit(7)")
        rows = self.run_workflow()
        self.assertEqual([row["outcome"] for row in rows], ["completato", "errore"])
        self.assertEqual(self.manager.outcome, "errore")

    def test_missing_requirement_blocks_script(self):
        self.activities[1].folder = self.root
        self.activities[1].filename = "required.xlsx"
        rows = self.run_workflow()
        self.assertEqual([row["outcome"] for row in rows], ["completato", "errore"])
        self.assertIsNone(rows[1]["exit_code"])
        self.assertNotIn("STEP_2", self.terminal.text)

    def test_cancel_and_concurrent_start_blocked(self):
        self.activities[0].script.write_text("import time\nprint('RUNNING',flush=True)\ntime.sleep(60)")
        self.assertTrue(self.manager.start(self.definition))
        self.assertFalse(self.manager.start(self.definition))
        self.assertFalse(self.execution.start(self.activities[1]))
        self.wait(lambda: "RUNNING" in self.terminal.text)
        self.manager.cancel()
        self.wait(lambda: not self.manager.active)
        self.assertEqual(self.manager.outcome, "interrotto")
        self.assertEqual(len(self.history.rows()), 1)
        self.assertEqual(self.history.workflows()[0]["outcome"], "interrotto")

    def test_output_must_be_updated_not_just_exist(self):
        (self.root / "report.xlsx").write_text("old")
        self.definition["steps"][0] = {"activity_id": "safe1", "outputs": [
            {"folder": str(self.root), "pattern": "report.xlsx", "changed": True}]}
        rows = self.run_workflow()
        self.assertEqual(rows[0]["exit_code"], 0)
        self.assertEqual(self.manager.outcome, "errore")
        self.assertEqual(len(rows), 1)

    def test_store_recovery_and_incomplete_session(self):
        store = WorkflowStore([a.activity_id for a in self.activities], self.root / "workflows.json")
        self.assertEqual(store.items, [])
        store.save(self.definition)
        store.load()
        self.assertEqual(store.items[0]["steps"][0]["activity_id"], "safe1")
        self.history.start_workflow("abandoned", "Previous session", ["safe1", "safe2"])
        self.history.start(self.activities[0], "abandoned", 0)
        self.history.recover()
        self.assertEqual(self.history.workflows()[0]["outcome"], "interrotto")
        self.assertEqual(self.history.rows()[0]["outcome"], "interrotto")
        self.assertFalse(self.manager.active)
        store.path.write_text('{"schema_version":1,"workflows":[{"id":"x","name":"Broken","steps":["unknown"]}]}')
        store.load()
        self.assertTrue(store.warning)
        self.assertEqual(store.items[0]["steps"], ["unknown"])

    def test_known_operational_failure_with_exit_zero(self):
        activity = replace(self.activities[0], activity_id="formatta_pedonalita")
        activity.script.write_text("print('[PEDONALITA] ERRORE, i 2 df non combaciano')")
        self.execution.status_service = None
        self.assertTrue(self.execution.start(activity))
        self.wait(lambda: not self.execution.busy)
        row = self.history.rows()[0]
        self.assertEqual((row["exit_code"], row["outcome"]), (0, "errore"))
