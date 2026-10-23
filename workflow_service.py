"""Manually configured sequential workflows; no inferred production chains."""
from copy import deepcopy
from dataclasses import replace
import fnmatch
import json
from pathlib import Path
import threading
from uuid import uuid4

from PySide6.QtCore import QObject, Signal, Slot, Qt
from operational_preferences import atomic_json, profile_dir


def validate_workflow(value, activity_ids):
    if not isinstance(value, dict) or not isinstance(value.get("id"), str) or not value["id"]:
        raise ValueError("ID workflow non valido")
    if not isinstance(value.get("name"), str) or not value["name"].strip():
        raise ValueError("Il workflow deve avere un nome")
    steps = value.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        raise ValueError("Inserisci da 1 a 100 passaggi")
    normalized = []
    for step in steps:
        step = {"activity_id": step} if isinstance(step, str) else deepcopy(step)
        if not isinstance(step, dict) or step.get("activity_id") not in activity_ids:
            raise ValueError("Il workflow contiene un'attività sconosciuta")
        outputs = step.get("outputs", [])
        if not isinstance(outputs, list):
            raise ValueError("Controlli output non validi")
        for rule in outputs:
            if not isinstance(rule, dict) or not isinstance(rule.get("folder"), str) or not Path(rule["folder"]).is_absolute():
                raise ValueError("Indica una cartella output assoluta")
            pattern = rule.get("pattern", "*")
            if not isinstance(pattern, str) or "/" in pattern or "\\" in pattern:
                raise ValueError("Il pattern output deve essere un nome file, senza cartelle")
            if type(rule.get("min_count", 1)) is not int or rule.get("min_count", 1) < 1:
                raise ValueError("Quantità output non valida")
            if type(rule.get("changed", True)) is not bool:
                raise ValueError("changed deve essere true o false")
        normalized.append(step)
    return {"id": value["id"], "name": value["name"].strip(), "steps": normalized}


class WorkflowStore:
    def __init__(self, activity_ids, path=None):
        self.activity_ids = set(activity_ids)
        self.path = Path(path) if path else profile_dir() / "workflows.json"
        self.items = []
        self.warning = ""
        self.load()

    def load(self):
        self.warning = ""
        if not self.path.exists():
            atomic_json(self.path, {"schema_version": 1, "workflows": []})
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("schema_version") != 1 or not isinstance(data.get("workflows"), list):
                raise ValueError("Formato workflow non supportato")
            # Preserve unknown definitions for correction instead of silently deleting them.
            self.items = data["workflows"]
            ids = [item["id"] for item in self.items]
            if len(ids) != len(set(ids)):
                raise ValueError("ID workflow duplicati")
            for item in self.items:
                validate_workflow(item, self.activity_ids)
        except (ValueError, OSError, AttributeError, KeyError, TypeError) as error:
            self.warning = f"Configurazione workflow non valida ({type(error).__name__}). Correggi il file prima di avviare."

    def save(self, workflow):
        if self.warning:
            raise ValueError(self.warning)
        workflow = validate_workflow(workflow, self.activity_ids)
        items = [item for item in self.items if item["id"] != workflow["id"]] + [workflow]
        atomic_json(self.path, {"schema_version": 1, "workflows": items})
        self.items = items

    def delete(self, workflow_id):
        if self.warning:
            raise ValueError(self.warning)
        items = [item for item in self.items if item["id"] != workflow_id]
        atomic_json(self.path, {"schema_version": 1, "workflows": items})
        self.items = items


def output_snapshot(rules):
    snapshots = []
    for rule in rules:
        folder = Path(rule["folder"])
        values = {}
        if folder.exists():
            for path in folder.iterdir():
                if fnmatch.fnmatch(path.name, rule.get("pattern", "*")) and path.is_file():
                    stat = path.stat()
                    values[path.name] = (stat.st_mtime_ns, stat.st_size)
        snapshots.append(values)
    return snapshots


class WorkflowManager(QObject):
    changed = Signal()
    finished = Signal(str)
    _db_done = Signal(object, object)

    def __init__(self, execution, activities, parent=None):
        super().__init__(parent)
        self.execution = execution
        self.activities = {a.activity_id: a for a in activities}
        self.active = False
        self.outcome = ""
        self.message = "Nessun workflow avviato."
        self.workflow = None
        self.run_id = None
        self.index = 0
        self.step_states = []
        self.cancel_requested = False
        self.pending = False
        self._db_done.connect(self._after_db, Qt.QueuedConnection)
        execution.finished.connect(self._step_done)

    def _async(self, operation, callback):
        self.pending = True
        def worker():
            try:
                result = (True, operation())
            except Exception as error:
                result = (False, type(error).__name__)
            self._db_done.emit(callback, result)
        threading.Thread(target=worker, daemon=True).start()

    @Slot(object, object)
    def _after_db(self, callback, result):
        self.pending = False
        if result[0]:
            callback(result[1])
        else:
            self.message = f"Workflow fermato: errore di controllo o salvataggio ({result[1]})."
            self._release("errore")

    def start(self, workflow):
        if self.active or self.execution.busy or self.execution.workflow_owner is not None:
            return False
        workflow = validate_workflow(workflow, self.activities)
        if not self.execution.profile_lock.tryLock(0):
            self.message = "Un'altra finestra sta eseguendo attività."
            self.changed.emit()
            return False
        self.execution.workflow_owner = self
        self.active, self.cancel_requested = True, False
        self.workflow, self.run_id, self.index = workflow, uuid4().hex, 0
        self.step_states = ["In attesa"] * len(workflow["steps"])
        self.outcome, self.message = "in_esecuzione", "Preparazione workflow…"
        self.changed.emit()
        self._async(lambda: self.execution.history.start_workflow(self.run_id, workflow["name"], workflow["steps"]),
                    lambda _: self._next())
        return True

    def _next(self):
        if self.cancel_requested:
            self._finish("interrotto")
            return
        if self.index >= len(self.workflow["steps"]):
            self._finish("completato")
            return
        step = self.workflow["steps"][self.index]
        self.step_states[self.index] = "Verifica in corso"
        self.message = f"Passaggio {self.index + 1}/{len(self.step_states)}: {self.activities[step['activity_id']].title}"
        self.changed.emit()
        self._async(lambda: output_snapshot(step.get("outputs", [])), self._launch)

    def _launch(self, before):
        if self.cancel_requested:
            self._finish("interrotto")
            return
        step = self.workflow["steps"][self.index]
        activity = replace(self.activities[step["activity_id"]])
        original_validator = activity.output_validator
        def validate():
            if original_validator:
                valid, message = original_validator()
                if not valid:
                    return valid, message
            after = output_snapshot(step.get("outputs", []))
            for rule, old, new in zip(step.get("outputs", []), before, after):
                matching = [name for name, stat in new.items() if not rule.get("changed", True) or old.get(name) != stat]
                if len(matching) < rule.get("min_count", 1):
                    return False, "Output mancanti o non aggiornati rispetto all'avvio del passaggio."
            return True, "Output verificati."
        activity.output_validator = validate
        self.step_states[self.index] = "In esecuzione"
        self.changed.emit()
        if not self.execution.start(activity, owner=self, workflow_run_id=self.run_id, step_index=self.index):
            self.step_states[self.index] = "Errore"
            self._finish("errore")

    def _step_done(self, result):
        if not self.active or self.execution.workflow_owner is not self:
            return
        outcome = "interrotto" if self.cancel_requested else result["outcome"]
        self.step_states[self.index] = {"completato": "Completato", "errore": "Errore", "interrotto": "Interrotto"}[outcome]
        self.changed.emit()
        if outcome != "completato":
            self._finish(outcome)
            return
        self.index += 1
        self._async(lambda: self.execution.history.update_workflow(self.run_id, self.index), lambda _: self._next())

    def _finish(self, outcome):
        self._async(lambda: self.execution.history.update_workflow(self.run_id, self.index, outcome),
                    lambda _: self._release(outcome))

    def _release(self, outcome):
        self.active = False
        self.outcome = outcome
        self.message = {"completato": "Workflow completato.", "errore": "Workflow fallito. Consulta lo storico.",
                        "interrotto": "Workflow interrotto dall'utente o dalla chiusura della sessione."}[outcome]
        self.execution.workflow_owner = None
        self.execution.profile_lock.unlock()
        self.changed.emit()
        self.finished.emit(outcome)

    def cancel(self):
        if self.active:
            self.cancel_requested = True
            self.message = "Interruzione in corso…"
            self.changed.emit()
            if self.execution.busy:
                self.execution.cancel()
