"""Small manual workflow editor and progress view using the existing Qt theme."""
from copy import deepcopy
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QDialogButtonBox, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from ui_theme import role, activity_icon
from operations_views import AsyncQuery, display_date, OUTCOMES
from workflow_service import validate_workflow


class WorkflowEditor(QDialog):
    def __init__(self, activities, definition=None, parent=None):
        super().__init__(parent)
        self.activities = {a.activity_id: a for a in activities}
        self.definition = deepcopy(definition) if definition else {"id": uuid4().hex, "name": "", "steps": []}
        self.setWindowTitle("Configura workflow")
        self.resize(620, 530)
        layout = QVBoxLayout(self)
        layout.addWidget(role(QLabel("Sequenza di attività"), "section"))
        hint = QLabel("Scegli l'ordine dei passaggi dopo aver verificato le dipendenze.\n"
                      "Ogni passaggio parte solo dopo il successo del precedente.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.name = QLineEdit(self.definition["name"])
        self.name.setPlaceholderText("Nome del workflow")
        layout.addWidget(self.name)
        row = QHBoxLayout()
        self.activity = QComboBox()
        for value in activities:
            self.activity.addItem(activity_icon(value.activity_id), value.title, value.activity_id)
        row.addWidget(self.activity, 1)
        add = QPushButton("Aggiungi passaggio")
        add.clicked.connect(lambda: self.add_step({"activity_id": self.activity.currentData()}))
        row.addWidget(add)
        layout.addLayout(row)
        self.steps = QListWidget()
        layout.addWidget(self.steps, 1)
        for step in self.definition["steps"]:
            self.add_step({"activity_id": step} if isinstance(step, str) else step)
        buttons = QHBoxLayout()
        for text, action in (("Sposta su", lambda: self.move(-1)), ("Sposta giù", lambda: self.move(1)),
                             ("Rimuovi", self.remove)):
            button = QPushButton(text)
            button.clicked.connect(action)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        footer = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        footer.accepted.connect(self.save)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

    def add_step(self, step):
        activity = self.activities.get(step["activity_id"])
        item = QListWidgetItem(activity_icon(step["activity_id"]), activity.title if activity else step["activity_id"])
        item.setData(Qt.UserRole, deepcopy(step))
        if step.get("outputs"):
            item.setToolTip("Include verifiche aggiuntive degli output configurate nel profilo.")
        self.steps.addItem(item)

    def move(self, delta):
        index = self.steps.currentRow()
        if index >= 0 and 0 <= index + delta < self.steps.count():
            item = self.steps.takeItem(index)
            self.steps.insertItem(index + delta, item)
            self.steps.setCurrentRow(index + delta)

    def remove(self):
        if self.steps.currentRow() >= 0:
            self.steps.takeItem(self.steps.currentRow())

    def save(self):
        try:
            self.definition = validate_workflow({"id": self.definition["id"], "name": self.name.text(),
                "steps": [self.steps.item(i).data(Qt.UserRole) for i in range(self.steps.count())]}, self.activities)
        except ValueError as error:
            self.error.setText(str(error))
            return
        self.accept()


class WorkflowPage(QWidget):
    def __init__(self, store, manager, activities, parent=None):
        super().__init__(parent)
        self.store, self.manager, self.activities = store, manager, activities
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(role(QLabel("Workflow"), "title"))
        hint = QLabel("Configura sequenze manuali. Il primo errore arresta la catena; nessun avvio automatico.")
        hint.setWordWrap(True)
        layout.addWidget(role(hint, "secondary"))
        toolbar = QHBoxLayout()
        self.selector = QComboBox()
        self.selector.setMinimumWidth(180)
        toolbar.addWidget(self.selector, 1)
        self.edit_controls = [self.selector]
        for text, callback in (("Nuovo", self.create), ("Modifica", self.edit), ("Elimina", self.delete), ("Ricarica", self.reload)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
            self.edit_controls.append(button)
        layout.addLayout(toolbar)
        self.state = role(QLabel(), "status")
        self.state.setWordWrap(True)
        layout.addWidget(self.state)
        self.progress = QListWidget()
        layout.addWidget(self.progress, 1)
        controls = QHBoxLayout()
        self.start_button = role(QPushButton("Avvia workflow"), "primary")
        self.start_button.clicked.connect(self.start)
        controls.addWidget(self.start_button)
        self.stop_button = QPushButton("Interrompi workflow")
        self.stop_button.clicked.connect(manager.cancel)
        controls.addWidget(self.stop_button)
        controls.addStretch()
        layout.addLayout(controls)
        layout.addWidget(role(QLabel("Ultimi workflow"), "section"))
        self.recent = QTableWidget(0, 3)
        self.recent.setShowGrid(False)
        self.recent.verticalHeader().setDefaultSectionSize(36)
        self.recent.setHorizontalHeaderLabels(["Workflow", "Avvio", "Esito"])
        self.recent.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.recent.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recent.verticalHeader().hide()
        self.recent.setMaximumHeight(160)
        layout.addWidget(self.recent)
        self.query = AsyncQuery(self)
        self.query.ready.connect(self.render_recent)
        manager.changed.connect(self.refresh)
        manager.finished.connect(self.load_recent)
        manager.execution.changed.connect(self.refresh)
        self.selector.currentIndexChanged.connect(self.refresh)
        self.reload()

    def selected(self):
        return next((x for x in self.store.items if isinstance(x, dict) and x.get("id") == self.selector.currentData()), None)

    def reload(self):
        self.store.load()
        selected = self.selector.currentData()
        self.selector.blockSignals(True)
        self.selector.clear()
        if not self.store.warning:
            for item in self.store.items:
                self.selector.addItem(item["name"], item["id"])
        index = self.selector.findData(selected)
        if index >= 0:
            self.selector.setCurrentIndex(index)
        self.selector.blockSignals(False)
        self.refresh()
        self.load_recent()

    def refresh(self, *_):
        manager = self.manager
        active = manager.active
        busy = active or manager.execution.busy
        for widget in self.edit_controls:
            widget.setEnabled(not busy)
        self.start_button.setEnabled(not busy and not self.store.warning and self.selected() is not None)
        self.stop_button.setEnabled(active and not manager.cancel_requested)
        self.state.setText(self.store.warning or manager.message if manager.workflow else
                           self.store.warning or "Nessun workflow avviato. Crea una sequenza per iniziare.")
        selected = self.selected()
        definition = manager.workflow if active or (manager.workflow and selected and
                     selected["id"] == manager.workflow["id"]) else selected
        self.progress.clear()
        if definition:
            names = {a.activity_id: a.title for a in self.activities}
            for index, step in enumerate(definition["steps"]):
                key = step if isinstance(step, str) else step["activity_id"]
                state = manager.step_states[index] if definition is manager.workflow else "In attesa"
                self.progress.addItem(QListWidgetItem(activity_icon(key), f"{index + 1}. {names.get(key, key)} · {state}"))

    def _edit(self, definition=None):
        dialog = WorkflowEditor(self.activities, definition, self)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.store.save(dialog.definition)
                self.reload()
                self.selector.setCurrentIndex(self.selector.findData(dialog.definition["id"]))
            except (ValueError, OSError) as error:
                QMessageBox.warning(self, "Workflow", str(error))

    def create(self):
        self._edit()

    def edit(self):
        if self.selected():
            self._edit(self.selected())

    def delete(self):
        value = self.selected()
        if value and QMessageBox.question(self, "Elimina workflow", f"Eliminare la definizione «{value['name']}»?") == QMessageBox.Yes:
            try:
                self.store.delete(value["id"])
                self.reload()
            except (ValueError, OSError) as error:
                QMessageBox.warning(self, "Workflow", str(error))

    def start(self):
        if self.selected():
            try:
                self.manager.start(self.selected())
            except ValueError as error:
                QMessageBox.warning(self, "Workflow", str(error))

    def load_recent(self, *_):
        if self.isVisible():
            self.query.run(self.manager.execution.history.workflows)

    def render_recent(self, result):
        rows = result.get("data", [])
        self.recent.setRowCount(len(rows))
        for index, row in enumerate(rows):
            for column, value in enumerate((row["name"], display_date(row["started_at"]), OUTCOMES[row["outcome"]])):
                self.recent.setItem(index, column, QTableWidgetItem(value))
