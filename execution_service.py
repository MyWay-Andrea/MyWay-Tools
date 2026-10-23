"""Single execution owner for modern and legacy launchers, workers and workflows."""
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QObject, Signal, Slot, Qt, QLockFile

from execution_history import HistoryStore, LogPolicy
from process_lifecycle import ProcessTree


class ExecutionService(QObject):
    started = Signal(object)
    finished = Signal(object)
    changed = Signal()
    _done = Signal(object)

    def __init__(self, terminal, python_finder, activities=(), history=None, parent=None):
        super().__init__(parent or terminal)
        self.terminal = terminal
        self.python_finder = python_finder
        self.activities = list(activities)
        self.history = history or HistoryStore()
        self.busy = False
        self.current = None
        self.tree = None
        self._tree_lock = threading.Lock()
        self.cancelled = threading.Event()
        self._callback = None
        self._generation = 0
        self.workflow_owner = None
        self.status_service = None
        self.profile_lock = QLockFile(str(self.history.path.with_name("execution.lock")))
        self.profile_lock.setStaleLockTime(0)
        if self.profile_lock.tryLock(0):
            self.history.recover()
            self.profile_lock.unlock()
        self._done.connect(self._complete, Qt.QueuedConnection)

    def launch_path(self, path, callback=None, **kwargs):
        path = Path(path).resolve()
        activity = next((a for a in self.activities if a.script and a.script.resolve() == path), None)
        if activity is None:
            activity = SimpleNamespace(activity_id="legacy:" + path.stem, title=path.stem, script=path)
        return self.start(activity, callback, **kwargs)

    def start(self, activity, callback=None, owner=None, workflow_run_id=None, step_index=None):
        if self.busy or (self.workflow_owner is not None and self.workflow_owner is not owner):
            self.terminal.write_safe("Avvio rifiutato: un'esecuzione o un workflow è già attivo.\n", "#E6B86A")
            return False
        if not self.profile_lock.isLocked() and not self.profile_lock.tryLock(0):
            self.terminal.write_safe("Avvio rifiutato: un'altra finestra sta eseguendo attività.\n", "#E6B86A")
            return False
        self.busy, self.current, self._callback = True, activity, callback
        self._generation += 1
        self.cancelled.clear()
        self.started.emit(activity)
        self.changed.emit()
        def checked(ready=True, message=""):
            threading.Thread(target=self._run, args=(activity, workflow_run_id, step_index, ready, message), daemon=True).start()
        if self.status_service and activity.activity_id in self.status_service.activities:
            self.status_service.check(activity, checked)
        else:
            checked()
        return True

    def _run(self, activity, workflow_run_id, step_index, ready=True, preflight_message=""):
        start = time.monotonic()
        run_id, code, outcome = None, None, "errore"
        policy = LogPolicy(self.history.settings, (value for key, value in os.environ.items()
                          if re.search(r"(?i)password|passwd|token|secret|api.?key", key)))
        pending, last_flush = [], time.monotonic()
        failure_seen = False
        # Existing scripts can report these failures and still exit with code zero.
        failure_patterns = {
            "formatta_pedonalita": r"\[PEDONALITA\].*ERRORE",
            "forecast_business": r"ATTENZIONE.*salto report",
        }

        def log(text, diagnostic=False):
            nonlocal last_flush, failure_seen
            if not diagnostic and re.search(failure_patterns.get(activity.activity_id, r"(?!)"), text, re.I):
                failure_seen = True
            # Original script output stays visible in the terminal, unchanged.
            self.terminal.write_safe(text, "#E0E0E0" if not diagnostic else "#8DB6DF")
            saved = policy.capture(text, diagnostic)
            if saved:
                pending.append(saved)
            if pending and (time.monotonic() - last_flush > .5 or sum(map(len, pending)) > 8192):
                self.history.append(run_id, "".join(pending))
                pending.clear()
                last_flush = time.monotonic()

        process = None
        try:
            run_id = self.history.start(activity, workflow_run_id, step_index)
            log(f"\nAvvio: {activity.title}\n", True)
            if self.cancelled.is_set():
                outcome = "interrotto"
                log("Interrotto prima dell'avvio del processo.\n", True)
                return
            if not ready:
                log("Requisiti non soddisfatti: elaborazione non avviata.\n", True)
                log(preflight_message + "\n")
                return
            if policy.mode != "redacted":
                self.history.append(run_id, "Log sintetico: output dello script consultabile nel terminale durante la sessione.\n")
            script = Path(activity.script).resolve() if activity.script else None
            if not script or not script.is_file():
                raise FileNotFoundError("Script non disponibile")
            env = os.environ.copy()
            env.update(PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
            bootstrap = (
                "import runpy, sys; from pathlib import Path; script = sys.argv[1]; "
                "sys.argv = sys.argv[1:]; sys.path.insert(0, str(Path(script).resolve().parent)); "
                "runpy.run_path(script, run_name='__main__')"
            )
            with self._tree_lock:
                if self.cancelled.is_set():
                    outcome = "interrotto"
                else:
                    self.tree = ProcessTree()
                    process = self.tree.launch([self.python_finder(), "-u", "-c", bootstrap, str(script)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        encoding="utf-8", errors="replace", env=env, cwd=str(script.parent))
            if process:
                with process.stdout:
                    for line in process.stdout:
                        log(re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", line))
                code = process.wait()
                outcome = "interrotto" if self.cancelled.is_set() else "completato" if code == 0 else "errore"
                if outcome == "completato" and failure_seen:
                    outcome = "errore"
                    log("Lo script ha segnalato un errore operativo nonostante exit 0.\n", True)
                validator = getattr(activity, "output_validator", None)
                if outcome == "completato" and validator:
                    valid, message = validator()
                    if not valid:
                        outcome = "errore"
                        log("Validazione output fallita.\n", True)
                        log(message + "\n")
            log(f"Esito: {outcome}" + (f" (exit {code})" if code is not None else "") + "\n", True)
        except Exception as error:
            outcome = "interrotto" if self.cancelled.is_set() else "errore"
            # Exception messages may embed credentials or document contents.
            if run_id:
                try:
                    log(f"Errore di esecuzione: {type(error).__name__}.\n", True)
                except Exception:
                    pass
            self.terminal.write_safe(f"Esecuzione non completata ({type(error).__name__}).\n", "#EE8D8D")
        finally:
            with self._tree_lock:
                if self.tree:
                    self.tree.close()
                    self.tree = None
            if process and process.poll() is None:
                process.kill()
                process.wait()
            if process and process.stdout and not process.stdout.closed:
                process.stdout.close()
            try:
                if run_id:
                    self.history.append(run_id, "".join(pending))
                    self.history.finish(run_id, outcome, code, time.monotonic() - start)
            except Exception:
                outcome = "errore"
                self.terminal.write_safe("Errore di salvataggio dello storico: controllare spazio e permessi del profilo.\n", "#EE8D8D")
            self._done.emit({"id": run_id, "activity_id": activity.activity_id,
                             "outcome": outcome, "exit_code": code})

    @Slot(object)
    def _complete(self, result):
        callback = self._callback
        self.busy, self.current, self._callback = False, None, None
        if self.workflow_owner is None:
            self.profile_lock.unlock()
        self.finished.emit(result)
        self.changed.emit()
        if callback:
            callback(result["outcome"] == "completato")

    def cancel(self):
        if not self.busy:
            return
        self.cancelled.set()
        generation = self._generation
        # Never wait on OS/process locks in the GUI thread.
        def stop():
            with self._tree_lock:
                if self.tree and generation == self._generation:
                    try:
                        self.tree.terminate()
                    except OSError:
                        self.terminal.write_safe("Interruzione non riuscita: il processo risulta ancora attivo.\n", "#EE8D8D")
        threading.Thread(target=stop, daemon=True).start()
