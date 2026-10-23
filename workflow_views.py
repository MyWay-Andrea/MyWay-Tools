"""Small manual workflow editor and progress view using the existing Qt theme."""
from copy import deepcopy
from uuid import uuid4
import time

from PySide6.QtCore import Qt, QTimer, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QDialogButtonBox, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QProgressBar, QStyledItemDelegate, QTextEdit,
)
from ui_theme import role, activity_icon, Theme
from ui_widgets import StyledComboBox as QComboBox
from operations_views import AsyncQuery, display_date, display_duration, OUTCOMES
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


class StepDelegate(QStyledItemDelegate):
    """Paint status marks, never interactive checkbox controls."""
    phase = 0

    def sizeHint(self, option, index):
        return QSize(240, 44)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(4, 2, -4, -2)
        state = index.data(Qt.UserRole)
        running = state in ("In esecuzione", "Verifica in corso")
        if running:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#EDF4FA"))
            painter.drawRoundedRect(rect, 8, 8)
        x, y = rect.left() + 20, rect.center().y()
        color = Theme.SUCCESS if state == "Completato" else Theme.ACCENT if state == "Errore" else Theme.MUTED
        painter.setPen(QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        if running:
            painter.setPen(Qt.NoPen)
            for dot in range(3):
                blue = QColor(Theme.INFO)
                blue.setAlpha(255 if dot == self.phase % 3 else 85)
                painter.setBrush(blue)
                painter.drawEllipse(QRectF(x - 9 + dot * 7, y - 2, 4, 4))
        elif state in ("In attesa", "Completato"):
            painter.drawRoundedRect(QRectF(x - 8, y - 8, 16, 16), 4, 4)
            if state == "Completato":
                painter.drawLine(x - 4, y, x - 1, y + 3)
                painter.drawLine(x - 1, y + 3, x + 5, y - 4)
        elif state == "Errore":
            painter.drawLine(x - 5, y - 5, x + 5, y + 5)
            painter.drawLine(x + 5, y - 5, x - 5, y + 5)
        else:
            painter.drawLine(x - 5, y, x + 5, y)
        painter.setPen(QColor(Theme.TEXT))
        text_rect = rect.adjusted(42, 0, -12, 0)
        text = index.data(Qt.DisplayRole)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft,
                         option.fontMetrics.elidedText(text, Qt.ElideRight, text_rect.width()))
        painter.restore()


class WorkflowMonitor(QFrame):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.run_id = None
        self.setObjectName("workflowMonitor")
        self.setStyleSheet(f"""
            QFrame#workflowMonitor {{ background:{Theme.SURFACE}; border:1px solid {Theme.BORDER}; border-radius:12px; }}
            QProgressBar {{ border:0; border-radius:4px; background:{Theme.SIDEBAR}; height:8px; }}
            QProgressBar::chunk {{ background:{Theme.INFO}; border-radius:4px; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        self.title = role(QLabel(), "section")
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.PlainText)
        layout.addWidget(self.title)
        self.state = role(QLabel(), "status")
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.PlainText)
        layout.addWidget(self.state)
        self.steps = QListWidget()
        self.steps.setAccessibleName("Avanzamento script del workflow")
        self.steps.setSelectionMode(QAbstractItemView.NoSelection)
        self.steps.setMinimumHeight(100)
        self.delegate = StepDelegate(self.steps)
        self.steps.setItemDelegate(self.delegate)
        self.steps.itemClicked.connect(self.show_step_log)
        layout.addWidget(self.steps, 1)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)
        row = QHBoxLayout()
        self.counter = QLabel()
        self.duration = role(QLabel(), "secondary")
        row.addWidget(self.counter)
        row.addStretch()
        row.addWidget(self.duration)
        layout.addLayout(row)
        controls = QHBoxLayout()
        self.logs_button = QPushButton("Mostra log")
        self.logs_button.clicked.connect(self.toggle_logs)
        controls.addWidget(self.logs_button)
        self.stop_button = QPushButton("Interrompi workflow")
        self.stop_button.clicked.connect(manager.cancel)
        controls.addWidget(self.stop_button)
        controls.addStretch()
        layout.addLayout(controls)
        self.log_title = role(QLabel(), "secondary")
        self.log_title.setTextFormat(Qt.PlainText)
        layout.addWidget(self.log_title)
        self.step_log = QTextEdit()
        self.step_log.setReadOnly(True)
        self.step_log.setMaximumHeight(150)
        self.step_log.setAccessibleName("Log del passaggio selezionato")
        layout.addWidget(self.step_log)
        self.log_title.hide()
        self.step_log.hide()
        self.log_query = AsyncQuery(self)
        self.log_query.ready.connect(self.render_step_log)
        self.log_key = None
        terminal = manager.execution.terminal
        terminal.collapsed_changed.connect(self.sync_logs_button)
        self.timer = QTimer(self)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.animate)

    def sync_logs_button(self, collapsed):
        self.logs_button.setText("Mostra log" if collapsed else "Nascondi log")

    def toggle_logs(self):
        terminal = self.manager.execution.terminal
        terminal.set_collapsed(not terminal._collapsed)

    def show_step_log(self, item):
        index = self.steps.row(item)
        run_id = self.manager.step_run_ids[index]
        if item.data(Qt.UserRole) not in ("Completato", "Errore", "Interrotto") or not run_id:
            return
        self.log_key = (self.manager.run_id, index, run_id)
        key = self.log_key
        self.log_title.setText(f"Log · {item.text()}")
        self.log_title.show()
        self.step_log.setPlainText("Caricamento log…")
        self.step_log.show()
        self.log_query.run(lambda: (key, self.manager.execution.history.detail(run_id)))

    def render_step_log(self, result):
        if "error" in result:
            self.step_log.setPlainText(result["error"])
            return
        key, row = result["data"]
        if key != self.log_key or key[0] != self.manager.run_id:
            return
        self.step_log.setPlainText(row["log"] if row else "Log non più disponibile nello storico.")

    def refresh(self):
        manager = self.manager
        if not manager.workflow:
            return
        if self.run_id != manager.run_id:
            self.run_id = manager.run_id
            self.log_key = None
            self.log_title.hide()
            self.step_log.hide()
            self.steps.clear()
            for index, step in enumerate(manager.workflow["steps"]):
                title = manager.activities[step["activity_id"]].title
                item = QListWidgetItem(f"{index + 1}. {title}")
                item.setData(Qt.UserRole + 1, (manager.run_id, index))
                self.steps.addItem(item)
        self.title.setText(manager.workflow["name"])
        self.state.setText(manager.message)
        for index, state in enumerate(manager.step_states):
            item = self.steps.item(index)
            item.setData(Qt.UserRole, state)
            item.setToolTip(f"{item.text()} · {state}")
            item.setData(Qt.AccessibleTextRole, f"{item.text()} · {state}")
        count = manager.step_states.count("Completato")
        self.bar.setRange(0, len(manager.step_states))
        self.bar.setValue(count)
        self.counter.setText(f"{count} / {len(manager.step_states)} script completati")
        self.stop_button.setEnabled(manager.active and not manager.cancel_requested)
        self.sync_logs_button(manager.execution.terminal._collapsed)
        self.update_duration()
        self.timer.start() if manager.active and self.isVisible() else self.timer.stop()

    def update_duration(self):
        manager = self.manager
        elapsed = (manager.ended_at or time.monotonic()) - manager.started_at if manager.started_at is not None else 0
        self.duration.setText(f"Durata totale: {display_duration(elapsed)}")

    def animate(self):
        # Only animate the dots and read the real clock. Progress comes from manager.changed.
        self.delegate.phase += 1
        self.steps.viewport().update()
        self.update_duration()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)


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
        self.monitor = WorkflowMonitor(manager, self)
        self.monitor.hide()
        layout.addWidget(self.monitor, 1)
        self.state = role(QLabel(), "status")
        self.state.setWordWrap(True)
        layout.addWidget(self.state)
        self.progress = QListWidget()
        layout.addWidget(self.progress, 1)
        controls = QHBoxLayout()
        self.start_button = role(QPushButton("Avvia workflow"), "primary")
        self.start_button.clicked.connect(self.start)
        controls.addWidget(self.start_button)
        self.stop_button = self.monitor.stop_button
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
        monitoring = definition is manager.workflow and manager.workflow is not None
        self.monitor.setVisible(monitoring)
        self.state.setVisible(not monitoring)
        self.progress.setVisible(not monitoring)
        if monitoring:
            self.monitor.refresh()
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
