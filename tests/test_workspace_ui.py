"""Run: python -B -m unittest discover -s tests -v

Business scripts and live SharePoint are never executed. Optional screenshots:
set MYWAY_UI_SCREENSHOTS to a temporary output directory.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

# The bundled embeddable Python runtime omits the working directory from sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QSize, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
import menu
from activity_status import ActivityState


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        # The Windows offscreen plugin does not discover system fonts.
        if not QFontDatabase.families():
            for name in ("segoeui.ttf", "seguisb.ttf", "segoeuib.ttf", "consola.ttf"):
                QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="myway-ui-test-")
        self.root = Path(self.temp.name)
        self.raw = self.root / "raw"
        self.raw.mkdir()
        self.env = patch.dict(os.environ)
        self.env.start()
        os.environ["APPDATA"] = str(self.root)
        self.window = menu.OperationsWindow(self.root, self.raw)
        self.window.showNormal()
        self.window.resize(1280, 800)
        self.app.processEvents()
        self.detail = self.window.hub.detail
        self.wait_until(lambda: not self.window.status_service.scanning)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.env.stop()
        self.temp.cleanup()

    def wait_until(self, predicate, timeout=5000):
        end = time.monotonic() + timeout / 1000
        while not predicate() and time.monotonic() < end:
            QTest.qWait(10)
        self.assertTrue(predicate(), "Timed out waiting for a GUI/worker signal")

    def test_sections_search_selection_and_empty_state(self):
        for section, count in {"today": 5, "all": 18, "business": 8, "consumer": 6, "campaigns": 4}.items():
            self.window.sidebar.buttons[section].click()
            self.assertEqual(len(self.window.hub.buttons), count)
            self.assertTrue(self.window.sidebar.buttons[section].isChecked())
            self.window.hub.buttons[-1].click()
            self.assertIs(self.detail.activity, self.window.hub.buttons[-1].activity)
            self.assertEqual(self.detail.title.text(), self.detail.activity.title)
        self.window.show_page("all")
        self.window.hub.search.setText("FORECAST")
        self.assertEqual(len(self.window.hub.buttons), 1)
        self.assertEqual(self.detail.title.text(), "Forecast Business")
        self.window.hub.search.setText("no-match-xyz")
        self.assertIsNone(self.detail.activity)
        self.assertFalse(self.detail.action.isEnabled())
        self.assertEqual(self.detail.instructions.text(), "")
        self.assertEqual(self.detail.folder.text(), "")
        self.window.sidebar.buttons["files"].click()
        self.assertIs(self.window.pages.currentWidget(), self.window.files_page)
        self.window.sidebar.buttons["today"].click()
        self.assertIs(self.window.pages.currentWidget(), self.window.hub)

    def test_favorite_star_does_not_select_or_launch(self):
        from operational_preferences import DEFAULT_FAVORITES, Favorites
        hub = self.window.hub
        self.assertEqual([a.activity_id for a in hub.visible_activities()], DEFAULT_FAVORITES)
        self.window.show_page("all")
        selected = hub.detail.activity
        row = next(b for b in hub.buttons if b.activity.activity_id == "elabora_cb")
        with patch.object(menu, "lancia_script") as launch:
            row.star.click()
            self.assertIs(hub.detail.activity, selected)
            launch.assert_not_called()
        self.window.show_page("today")
        self.assertEqual(len(hub.buttons), 6)
        hub.buttons[-1].star.click()
        self.assertEqual(len(hub.buttons), 5)
        loaded = Favorites([a.activity_id for a in self.window.activities], self.window.favorites.path)
        self.assertEqual(loaded.ids, DEFAULT_FAVORITES)

    def test_workflow_editor_and_navigation(self):
        from workflow_views import WorkflowEditor
        editor = WorkflowEditor(self.window.activities, parent=self.window)
        editor.name.setText("Sequenza manuale")
        editor.add_step({"activity_id": "estrai_file_gara"})
        editor.add_step({"activity_id": "forecast_business"})
        editor.steps.setCurrentRow(1)
        editor.move(-1)
        editor.save()
        self.window.workflow_store.save(editor.definition)
        self.window.workflow_page.reload()
        self.window.show_page("workflows")
        self.assertIs(self.window.pages.currentWidget(), self.window.workflow_page)
        self.assertTrue(self.window.workflow_page.start_button.isEnabled())
        self.assertIn("Forecast", self.window.workflow_page.progress.item(0).text())
        self.assertFalse(self.window.workflow_manager.active)
        self.wait_until(lambda: self.window.workflow_page.query.version > 0)
        QTest.qWait(50)
        editor.deleteLater()

    def test_script_bindings_and_lock_across_refresh_and_navigation(self):
        with patch.object(menu, "lancia_script", side_effect=lambda *args: menu.global_signals.script_avviato.emit()) as launch:
            for activity in self.window.activities:
                if not activity.available or activity.filename or activity.remote_check:
                    continue
                self.detail.set_activity(activity)
                self.detail.action.click()
                self.assertEqual(launch.call_args.args[:2], (activity.script, self.window.terminal))
                self.assertTrue(self.detail.busy)
                self.detail.refresh()
                self.window.show_page("consumer")
                self.detail.refresh()
                self.assertFalse(self.detail.action.isEnabled())
                calls = launch.call_count
                self.detail.run_or_prepare()
                self.assertEqual(launch.call_count, calls)
                menu.global_signals.script_terminato.emit()
                self.assertFalse(self.detail.busy)
            self.detail.set_activity(next(a for a in self.window.activities if a.title == "Report campagne"))
            self.assertFalse(self.detail.action.isEnabled())

    def test_keyboard_navigation_and_timer_lock(self):
        hub = self.window.hub
        hub.buttons[0].setFocus()
        QTest.keyClick(hub.buttons[0], Qt.Key_Down)
        self.app.processEvents()
        self.assertIs(self.detail.activity, hub.buttons[1].activity)
        with patch.object(menu, "lancia_script", side_effect=lambda *args: menu.global_signals.script_avviato.emit()) as launch:
            self.detail.action.click()
            QTest.qWait(3100)
            self.assertTrue(self.detail.busy)
            self.assertFalse(self.detail.action.isEnabled())
            self.window.show_page("all")
            hub.search.setText("Elabora CB")
            self.assertFalse(self.detail.action.isEnabled())
            menu.global_signals.script_terminato.emit()
            self.assertTrue(self.detail.action.isEnabled())

    def test_raw_counts_and_inline_upload(self):
        activity = next(a for a in self.window.activities if a.expected_count == 10)
        self.detail.set_activity(activity)
        self.assertFalse(activity.readiness()[0])
        for i in range(9):
            (self.raw / f"AVANZAMENTI_{i}.xlsx").write_bytes(b"test input")
        self.window.status_service.refresh()
        self.wait_until(lambda: not self.window.status_service.scanning)
        self.assertIn("9/10", self.detail.status.text())
        source = self.root / "AVANZAMENTI_9.xlsx"
        source.write_bytes(b"test input")
        with patch.object(QFileDialog, "getOpenFileNames", return_value=([str(source)], "")):
            self.detail.action.click()
        self.window.status_service.refresh()
        self.wait_until(lambda: activity.readiness()[0])
        self.assertTrue(activity.readiness()[0])
        self.assertEqual(self.detail.action.text(), "Esegui attività")
        (self.raw / "AVANZAMENTI_extra.xlsx").write_bytes(b"test input")
        self.window.status_service.refresh()
        self.wait_until(lambda: not self.window.status_service.scanning)
        self.assertFalse(activity.readiness()[0])
        self.assertIn("eccesso", self.detail.status.text())
        with patch.object(menu, "lancia_script") as launch, patch.object(
                QFileDialog, "getOpenFileNames", return_value=([], "")):
            self.detail.action.click()
            launch.assert_not_called()

    def test_drop_delete_and_folder_configuration(self):
        self.window.show_page("files")
        widget = self.window.files_page.raw_files_widget
        source = self.root / "input.csv"
        source.write_text("value\n1\n")
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(source))])
        enter = QDragEnterEvent(QPoint(20, 20), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(widget, enter)
        self.assertTrue(enter.isAccepted())
        drop = QDropEvent(QPointF(20, 20), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(widget, drop)
        copied = self.raw / source.name
        self.assertEqual(copied.read_bytes(), source.read_bytes())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            widget._elimina_file(copied)
        self.assertFalse(copied.exists())
        new_raw = self.root / "new_raw"
        new_raw.mkdir()
        config = self.root / "profile" / "config.json"
        with patch.object(menu, "CONFIG_PATH", config), patch.object(
                QFileDialog, "getExistingDirectory", return_value=str(new_raw)):
            widget._scegli_cartella()
        self.assertEqual(json.loads(config.read_text())["raw_files_path"], str(new_raw))
        self.assertEqual(self.window.paths["RAW_FILES"], new_raw)
        self.assertTrue(all(a.folder == new_raw for a in self.window.activities if a.filename))

    def test_remote_preflight_results_and_selection_race(self):
        activity = next(a for a in self.window.activities if a.remote_check)
        self.detail.set_activity(activity)
        result = subprocess.CompletedProcess([], 0, '__MYWAY_CB_CHECK__{"found":true,"name":"CB.xlsx"}\n', "")
        with patch.object(menu.subprocess, "run", return_value=result) as remote, patch.object(menu, "lancia_script") as launch:
            self.detail.action.click()
            self.wait_until(lambda: not self.detail.remote_checker.running)
            self.assertIn("CB.xlsx", self.detail.status.text())
            launch.assert_not_called()
            self.detail.action.click()
            self.assertEqual(launch.call_args.args[0], activity.script)
            self.window.status_service.states[activity.activity_id] = ActivityState(available=True)
            menu.global_signals.script_terminato.emit()
            self.assertEqual(remote.call_args.kwargs["timeout"], 40)
        with patch.object(menu.subprocess, "run", side_effect=subprocess.TimeoutExpired("check", 40)):
            self.detail.action.click()
            self.wait_until(lambda: not self.detail.remote_checker.running)
            self.assertIn("40 secondi", self.detail.status.text())
            self.assertEqual(self.detail.action.text(), "Verifica SharePoint")
        result = subprocess.CompletedProcess([], 0, '__MYWAY_CB_CHECK__{"found":false}\n', "")
        with patch.object(menu.subprocess, "run", return_value=result):
            self.detail.action.click()
            self.detail.set_activity(self.window.activities[0])
            self.wait_until(lambda: not self.detail.remote_checker.running)
            self.assertIn(self.window.activities[0].readiness()[1], self.detail.status.text())

    def test_terminal_real_streaming_and_persistence(self):
        terminal = self.window.terminal
        script = self.root / "harmless_stream.py"
        script.write_text("import time\nprint('FIRST_LOG', flush=True)\ntime.sleep(0.6)\nprint('LAST_LOG', flush=True)\n")
        with patch.object(menu, "_trova_python", return_value=sys.executable), patch.object(
                self.window.activities[0], "script", script):
            self.detail.action.click()
            self.assertTrue(self.detail.busy)
            self.assertFalse(terminal._collapsed)
            self.assertTrue(terminal.log.isVisible())
            self.wait_until(lambda: "FIRST_LOG" in terminal.log.toPlainText())
            self.assertNotIn("LAST_LOG", terminal.log.toPlainText())
            terminal.btn_toggle.click()
            self.window.show_page("files")
            self.wait_until(lambda: not self.detail.busy)
        self.app.processEvents()
        self.assertIn("LAST_LOG", terminal.log.toPlainText())
        self.assertEqual(terminal.state.text(), "Pronto")
        self.window.show_page("business")
        terminal.btn_toggle.click()
        self.assertIn("FIRST_LOG", terminal.log.toPlainText())
        terminal.btn_toggle.click()
        menu.global_signals.script_avviato.emit()
        self.assertTrue(terminal.log.isVisible())
        self.assertEqual(terminal.btn_toggle.text(), "Nascondi")
        self.assertGreater(self.window.splitter.sizes()[1], menu.Theme.TERMINAL_HEADER)
        menu.global_signals.script_terminato.emit()
        terminal.btn_clear.click()
        self.assertEqual(terminal.log.toPlainText(), "")

    def test_subprocess_failure_and_missing_file(self):
        script = self.root / "harmless_failure.py"
        script.write_text("raise SystemExit(3)\n")
        completed = []
        with patch.object(menu, "_trova_python", return_value=sys.executable):
            menu.lancia_script(script, self.window.terminal, completed.append)
            self.wait_until(lambda: bool(completed))
        self.app.processEvents()
        self.assertEqual(completed, [False])
        self.assertIn("exit 3", self.window.terminal.log.toPlainText())
        menu.lancia_script(self.root / "missing.py", self.window.terminal, completed.append)
        self.wait_until(lambda: len(completed) == 2)
        self.assertEqual(completed, [False, False])

    def test_resize_splitters_and_screenshots(self):
        from ui_theme import ACTIVITY_ICONS, activity_icon
        self.assertEqual(set(ACTIVITY_ICONS), {a.activity_id for a in self.window.activities})
        for scale in (1, 1.25, 1.5, 2):
            pixmap = menu.line_icon("business").pixmap(QSize(20, 20), scale)
            self.assertEqual(pixmap.width(), round(20 * scale))
            self.assertEqual(pixmap.deviceIndependentSize().width(), 20)
            colored = activity_icon("forecast_business").pixmap(QSize(32, 32), scale)
            self.assertEqual(colored.width(), round(32 * scale))
        output = os.environ.get("MYWAY_UI_SCREENSHOTS")
        if output:
            Path(output).mkdir(parents=True, exist_ok=True)
        for width, height in ((1280, 800), (1600, 900), (1920, 1080), (1024, 640)):
            self.window.resize(width, height)
            self.app.processEvents()
            self.assertEqual((self.window.width(), self.window.height()), (width, height))
            self.assertEqual(self.window.sidebar.width(), menu.Theme.SIDEBAR_WIDTH)
            self.assertTrue(all(size >= 330 for size in self.window.hub.splitter.sizes()))
            self.assertEqual(self.window.hub.scroll.horizontalScrollBar().maximum(), 0)
            self.assertEqual(self.detail.scroll.horizontalScrollBar().maximum(), 0)
            self.assertTrue(self.detail.action.isVisible())
            if output:
                self.window.grab().save(str(Path(output) / f"workspace-{width}x{height}.png"))
        self.window.resize(1280, 800)
        self.window.hub.splitter.setSizes([360, 688])
        self.window.hub.select_activity(next(a for a in self.window.activities if a.expected_count == 10))
        self.window.terminal.set_collapsed(False)
        self.window.splitter.setSizes([400, 396])
        self.app.processEvents()
        self.assertGreater(self.detail.scroll.verticalScrollBar().maximum(), 0)
        self.assertTrue(self.detail.action.isVisible())
        if output:
            self.window.grab().save(str(Path(output) / "workspace-terminal.png"))
            self.window.show_page("files")
            self.app.processEvents()
            self.window.grab().save(str(Path(output) / "workspace-files.png"))

    def test_real_entrypoint_and_updater_hook(self):
        profile = self.root / "MyWayTools"
        profile.mkdir(exist_ok=True)
        (profile / "config.json").write_text(json.dumps({
            "sharepoint_root": str(self.root), "raw_files_path": str(self.raw)}))
        (profile / ".env").write_text("")  # Prevent access to real secrets.
        code = '''
import runpy
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
original_exec = QApplication.exec
def limited_exec(self):
    QTimer.singleShot(1400, self.quit)
    return original_exec()
with patch.object(QApplication, "exec", limited_exec), patch("updater.check_and_update", side_effect=lambda app: print("UPDATER_HOOK_OK")):
    runpy.run_path("menu.py", run_name="__main__")
'''
        env = os.environ.copy()
        env["APPDATA"] = str(self.root)
        result = subprocess.run([sys.executable, "-B", "-c", code], env=env,
                                capture_output=True, text=True, timeout=15,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("UPDATER_HOOK_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
