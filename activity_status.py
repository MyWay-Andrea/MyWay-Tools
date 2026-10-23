"""Cached readiness for the GUI; filesystem and remote checks execute in workers."""
from dataclasses import dataclass, replace
import threading
import time

from PySide6.QtCore import QObject, Signal, Slot, Qt, QTimer, QFileSystemWatcher


@dataclass(frozen=True)
class ActivityState:
    name: str = "Verifica in corso"
    message: str = "Requisiti non ancora verificati."
    available: bool = False
    checked_at: float = 0

    @property
    def ready(self):
        return self.name == "Pronto"


def inspect_activity(activity):
    try:
        available = bool(activity.script and activity.script.is_file())
        if not available:
            return ActivityState("Non disponibile", "Script non disponibile.", False, time.monotonic())
        ready, message = activity.evaluate_requirements()
        if activity.remote_check and ready:
            return ActivityState("Verifica in corso", "Verifica SharePoint richiesta prima dell'avvio.", True)
        return ActivityState("Pronto" if ready else "File mancanti", message, True, time.monotonic())
    except OSError:
        return ActivityState("Errore di verifica", "Impossibile leggere script o cartella dei requisiti.", False, time.monotonic())
    except Exception:
        return ActivityState("Errore di verifica", "Controllo dei requisiti non completato.", False, time.monotonic())


class StatusService(QObject):
    changed = Signal()
    _local_done = Signal(int, object)
    _check_done = Signal(object, object, object)

    def __init__(self, activities, remote_checker, parent=None):
        super().__init__(parent)
        self.activities = {a.activity_id: a for a in activities}
        self.states = {key: ActivityState() for key in self.activities}
        self.remote_checker = remote_checker
        remote_checker.finished.connect(self._remote_done)
        self.remote_id = None
        self.remote_callbacks = []
        self.generation = 0
        self.scanning = False
        self.dirty = False
        self.running_id = None
        self._local_done.connect(self._apply_local, Qt.QueuedConnection)
        self._check_done.connect(self._apply_check, Qt.QueuedConnection)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.invalidate)
        self.watcher.fileChanged.connect(self.invalidate)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(250)
        self.debounce.timeout.connect(self.refresh)
        self.fallback = QTimer(self)
        self.fallback.setInterval(30000)
        self.fallback.timeout.connect(self.refresh)
        self.fallback.start()
        self.rewatch()
        self.refresh()

    def state(self, activity):
        current = self.states[activity.activity_id]
        if self.running_id == activity.activity_id:
            return replace(current, name="In esecuzione", message="Attività in esecuzione.")
        return current

    def rewatch(self):
        paths = self.watcher.directories() + self.watcher.files()
        if paths:
            self.watcher.removePaths(paths)
        # Only register paths; the actual stat/glob work is always asynchronous.
        paths = {str(a.folder) for a in self.activities.values() if a.folder}
        paths.update(str(a.script.parent) for a in self.activities.values() if a.script)
        if paths:
            self.watcher.addPaths(list(paths))

    def invalidate(self, *_):
        self.generation += 1
        for key, activity in self.activities.items():
            if activity.filename:
                self.states[key] = ActivityState(message="Cartella modificata: verifica in corso.",
                                                 available=self.states[key].available)
        self.changed.emit()
        self.debounce.start()

    def raw_changed(self):
        self.rewatch()
        self.invalidate()
        self.refresh()

    def refresh(self):
        if self.scanning:
            self.dirty = True
            return
        self.scanning = True
        generation = self.generation
        snapshots = [replace(activity) for activity in self.activities.values()]
        def worker():
            results = {a.activity_id: inspect_activity(a) for a in snapshots}
            try:
                self._local_done.emit(generation, results)
            except RuntimeError:
                pass
        threading.Thread(target=worker, daemon=True).start()

    @Slot(int, object)
    def _apply_local(self, generation, results):
        self.scanning = False
        if generation == self.generation:
            for key, value in results.items():
                previous = self.states[key]
                if self.activities[key].remote_check and value.available:
                    if self.remote_id == key or (previous.checked_at and time.monotonic() - previous.checked_at < 60):
                        continue
                self.states[key] = value
            self.changed.emit()
        if self.dirty or generation != self.generation:
            self.dirty = False
            self.refresh()

    def check(self, activity, callback, force_remote=True):
        """Fresh preflight immediately before each launch, never trust a UI cache."""
        snapshot = replace(activity)
        generation = self.generation
        def worker():
            value = inspect_activity(snapshot)
            try:
                self._check_done.emit((activity.activity_id, generation, force_remote), value, callback)
            except RuntimeError:
                pass
        threading.Thread(target=worker, daemon=True).start()

    @Slot(object, object, object)
    def _apply_check(self, request, value, callback):
        key, generation, force_remote = request
        if generation != self.generation:
            callback(False, "La cartella RAW è cambiata durante la verifica. Riprova.")
            return
        self.states[key] = value
        self.changed.emit()
        if self.activities[key].remote_check and value.available:
            self.check_remote(self.activities[key], callback)
        else:
            callback(value.ready, value.message)

    def check_remote(self, activity, callback=None):
        if self.remote_id and self.remote_id != activity.activity_id:
            if callback:
                callback(False, "Un'altra verifica remota è già in corso.")
            return
        if callback:
            self.remote_callbacks.append(callback)
        if self.remote_checker.running:
            return
        self.remote_id = activity.activity_id
        self.states[self.remote_id] = ActivityState("Verifica in corso", "Verifica SharePoint in corso…", True)
        self.remote_checker.start()
        self.changed.emit()

    @Slot(bool, str)
    def _remote_done(self, ready, message):
        if not self.remote_id:
            return
        key = self.remote_id
        name = "Pronto" if ready else "File mancanti" if message.startswith("Nessun file") else "Errore di verifica"
        self.states[key] = ActivityState(name, message, True, time.monotonic())
        self.remote_id = None
        callbacks, self.remote_callbacks = self.remote_callbacks, []
        self.changed.emit()
        for callback in callbacks:
            callback(ready, message)

    def started(self, activity):
        self.running_id = activity.activity_id if activity.activity_id in self.activities else None
        self.changed.emit()

    def finished(self, *_):
        if self.running_id in self.states:
            key = self.running_id
            self.states[key] = ActivityState(available=self.states[key].available)
        self.running_id = None
        self.refresh()
