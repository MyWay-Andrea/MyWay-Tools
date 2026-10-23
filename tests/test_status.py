import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from activity_status import StatusService
from menu import ActivitySpec


class FakeRemote(QObject):
    finished = Signal(bool, str)
    running = False

    def start(self):
        self.running = True

    def complete(self, ready, message):
        self.running = False
        self.finished.emit(ready, message)


class StatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait(self, condition):
        end = time.monotonic() + 5
        while not condition() and time.monotonic() < end:
            QTest.qWait(10)
        self.assertTrue(condition())

    def test_async_counts_error_watcher_and_fresh_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "safe.py"
            script.write_text("pass")
            activity = ActivitySpec(1, "Safe", "", "Consumer", script, None, root, "*.csv",
                                    expected_count=2, activity_id="safe")
            remote = FakeRemote()
            service = StatusService([activity], remote)
            activity.status_service = service
            self.wait(lambda: not service.scanning)
            self.assertEqual(service.state(activity).name, "File mancanti")
            (root / "a.csv").write_text("")
            (root / "b.csv").write_text("")
            self.wait(lambda: activity.readiness()[0])  # Real QFileSystemWatcher notification.
            (root / "extra.csv").write_text("")
            self.wait(lambda: "eccesso" in activity.readiness()[1])
            # Slow reads leave the Qt event loop responsive.
            entered, release = threading.Event(), threading.Event()
            def slow(_):
                entered.set()
                release.wait(2)
                raise PermissionError()
            with patch.object(ActivitySpec, "evaluate_requirements", slow):
                service.refresh()
                self.wait(entered.is_set)
                heartbeat = []
                QTimer.singleShot(0, lambda: heartbeat.append(True))
                self.wait(lambda: bool(heartbeat))
                release.set()
                self.wait(lambda: not service.scanning)
            self.assertEqual(service.state(activity).name, "Errore di verifica")
            service.fallback.stop()
            service.debounce.stop()
            service.deleteLater()
            QTest.qWait(20)

    def test_remote_not_ready_until_verified_and_fresh_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "safe.py"
            script.write_text("pass")
            activity = ActivitySpec(1, "Remote", "", "Business", script, None,
                                    remote_check="sharepoint_cb", activity_id="remote")
            self.assertFalse(activity.readiness()[0])
            remote = FakeRemote()
            service = StatusService([activity], remote)
            activity.status_service = service
            self.wait(lambda: not service.scanning)
            self.assertFalse(activity.readiness()[0])
            service.check_remote(activity)
            remote.complete(True, "File CB trovato")
            self.assertTrue(activity.readiness()[0])
            result = []
            service.check(activity, lambda *args: result.append(args))
            self.wait(lambda: remote.running)
            self.assertEqual(result, [])
            remote.complete(False, "Nessun file CB trovato")
            self.assertEqual(result, [(False, "Nessun file CB trovato")])
            self.assertEqual(service.state(activity).name, "File mancanti")
            service.check_remote(activity)
            remote.complete(False, "Impossibile verificare SharePoint")
            self.assertEqual(service.state(activity).name, "Errore di verifica")
            service.fallback.stop()
            service.deleteLater()
            QTest.qWait(20)
