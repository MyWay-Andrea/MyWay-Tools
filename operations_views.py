"""Secondary operational views. Database queries always run outside the GUI thread."""
from datetime import datetime
import threading

from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QTextEdit, QMessageBox,
)
from ui_theme import role, activity_icon, Theme

OUTCOMES = {"completato": "Completato", "errore": "Errore", "interrotto": "Interrotto",
            "in_esecuzione": "In esecuzione"}


def display_date(value):
    return datetime.fromisoformat(value).astimezone().strftime("%d/%m/%Y %H:%M:%S") if value else "—"


def display_duration(value):
    if value is None:
        return "—"
    return f"{int(value) // 60}m {value % 60:.1f}s"


class AsyncQuery(QObject):
    ready = Signal(object)
    _result = Signal(int, object)

    def __init__(self, parent):
        super().__init__(parent)
        self.version = 0
        self._result.connect(self._deliver, Qt.QueuedConnection)

    def run(self, function):
        self.version += 1
        version = self.version
        def worker():
            try:
                result = {"data": function()}
            except Exception as error:
                result = {"error": f"Operazione non completata ({type(error).__name__})."}
            try:
                self._result.emit(version, result)
            except RuntimeError:
                pass  # Window closed while a read-only query was pending.
        threading.Thread(target=worker, daemon=True).start()

    @Slot(int, object)
    def _deliver(self, version, result):
        if version == self.version:
            self.ready.emit(result)


class HistoryPage(QWidget):
    def __init__(self, store, activities, parent=None):
        super().__init__(parent)
        self.store = store
        self.offset = 0
        self.rows = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(role(QLabel("Storico delle esecuzioni"), "title"))
        self.note = role(QLabel("Log sintetici per impostazione predefinita. Conservazione: "
                               f"{store.settings['retention_days']} giorni."), "secondary")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        filters = QHBoxLayout()
        self.activity_filter = QComboBox()
        self.activity_filter.addItem("Tutte le attività", None)
        for activity in activities:
            self.activity_filter.addItem(activity.title, activity.activity_id)
        self.outcome_filter = QComboBox()
        self.outcome_filter.addItem("Tutti gli esiti", None)
        for key, label in OUTCOMES.items():
            self.outcome_filter.addItem(label, key)
        for control in (self.activity_filter, self.outcome_filter):
            filters.addWidget(control)
            control.currentIndexChanged.connect(self.reset_filter)
        refresh = QPushButton("Aggiorna")
        refresh.clicked.connect(self.refresh)
        filters.addWidget(refresh)
        layout.addLayout(filters)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Attività", "Data e ora", "Durata", "Esito"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.cellDoubleClicked.connect(self.open_detail)
        layout.addWidget(self.table, 1)
        footer = QHBoxLayout()
        self.previous = QPushButton("Più recenti")
        self.next = QPushButton("Precedenti")
        self.previous.clicked.connect(lambda: self.turn_page(-1))
        self.next.clicked.connect(lambda: self.turn_page(1))
        footer.addWidget(self.previous)
        footer.addWidget(self.next)
        detail = QPushButton("Apri dettaglio e log")
        detail.clicked.connect(lambda: self.open_detail(self.table.currentRow()))
        footer.addWidget(detail)
        footer.addStretch()
        clear = QPushButton("Elimina storico")
        clear.clicked.connect(self.clear_history)
        footer.addWidget(clear)
        layout.addLayout(footer)
        self.query = AsyncQuery(self)
        self.query.ready.connect(self.render)
        self.detail_query = AsyncQuery(self)
        self.detail_query.ready.connect(self.show_detail)
        self.clear_query = AsyncQuery(self)
        self.clear_query.ready.connect(self._cleared)

    def reset_filter(self):
        self.offset = 0
        self.refresh()

    def turn_page(self, delta):
        self.offset = max(0, self.offset + delta * 100)
        self.refresh()

    def refresh(self, *_):
        if not self.isVisible():
            return
        activity, outcome, offset = self.activity_filter.currentData(), self.outcome_filter.currentData(), self.offset
        self.query.run(lambda: self.store.rows(activity, outcome, 100, offset))

    def render(self, result):
        if "error" in result:
            self.note.setText(result["error"])
            return
        self.rows = result["data"]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for index, row in enumerate(self.rows):
            values = (row["activity_name"], display_date(row["started_at"]),
                      display_duration(row["duration"]), OUTCOMES[row["outcome"]])
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, row["id"])
                if column == 0:
                    item.setIcon(activity_icon(row["activity_id"]))
                if column == 3:
                    item.setForeground(QColor(Theme.SUCCESS if row["outcome"] == "completato" else
                                              "#B42332" if row["outcome"] == "errore" else Theme.MUTED))
                self.table.setItem(index, column, item)
        self.previous.setEnabled(self.offset > 0)
        self.next.setEnabled(len(self.rows) == 100)
        self.note.setText("Nessuna esecuzione per questi filtri." if not self.rows else
                          f"{len(self.rows)} esecuzioni, dalla più recente. Conservazione: {self.store.settings['retention_days']} giorni.")

    def open_detail(self, row, *_):
        item = self.table.item(row, 0)
        if item:
            run_id = item.data(Qt.UserRole)
            self.detail_query.run(lambda: self.store.detail(run_id))

    def show_detail(self, result):
        row = result.get("data")
        if not row:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(row["activity_name"])
        dialog.resize(800, 600)
        layout = QVBoxLayout(dialog)
        label = QLabel(f"{OUTCOMES[row['outcome']]} · {display_duration(row['duration'])} · exit {row['exit_code']}\n"
                       f"Avvio: {display_date(row['started_at'])} · Fine: {display_date(row['ended_at'])}\n"
                       f"ID: {row['id']}" + (f"\nWorkflow: {row['workflow_run_id']} · Passaggio {row['step_index'] + 1}" if row['workflow_run_id'] else ""))
        label.setWordWrap(True)
        layout.addWidget(label)
        log = QTextEdit()
        log.setReadOnly(True)
        log.setPlainText(row["log"] or "Nessun log salvato.")
        layout.addWidget(log)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.show()

    def clear_history(self):
        if QMessageBox.question(self, "Elimina storico", "Eliminare tutte le esecuzioni concluse e i relativi log?") == QMessageBox.Yes:
            self.clear_query.run(self.store.clear)

    def _cleared(self, result):
        if "error" in result:
            self.note.setText(result["error"])
        else:
            self.offset = 0
            self.refresh()
