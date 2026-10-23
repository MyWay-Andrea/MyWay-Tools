"""Secondary operational views. Database queries always run outside the GUI thread."""
from datetime import datetime
import threading

from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QTextEdit, QMessageBox,
    QGridLayout, QFrame, QScrollArea,
)
from ui_theme import role, activity_icon, Theme
from ui_widgets import StyledComboBox as QComboBox

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
        self.running = False
        self.pending = None
        self._result.connect(self._deliver, Qt.QueuedConnection)

    def run(self, function):
        self.version += 1
        version = self.version
        if self.running:
            self.pending = (version, function)
            return
        self._start(version, function)

    def _start(self, version, function):
        self.running = True
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
        self.running = False
        if version == self.version:
            self.ready.emit(result)
        if self.pending:
            request, self.pending = self.pending, None
            self._start(*request)


class HistoryPage(QWidget):
    history_cleared = Signal()
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
            self.activity_filter.addItem(activity_icon(activity.activity_id), activity.title, activity.activity_id)
        self.outcome_filter = QComboBox()
        self.outcome_filter.addItem("Tutti gli esiti", None)
        for key, label in OUTCOMES.items():
            self.outcome_filter.addItem(label, key)
        for control in (self.activity_filter, self.outcome_filter):
            filters.addWidget(control)
            control.currentIndexChanged.connect(self.reset_filter)
        self.order = QComboBox()
        self.order.addItem("Più recenti prima", True)
        self.order.addItem("Meno recenti prima", False)
        self.order.currentIndexChanged.connect(self.reset_filter)
        filters.addWidget(self.order)
        refresh = QPushButton("Aggiorna")
        refresh.clicked.connect(self.refresh)
        filters.addWidget(refresh)
        layout.addLayout(filters)
        self.table = QTableWidget(0, 4)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
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
        newest_first = self.order.currentData()
        self.query.run(lambda: self.store.rows(activity, outcome, 100, offset, newest_first))

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
                          f"{len(self.rows)} esecuzioni. Conservazione: {self.store.settings['retention_days']} giorni.")

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
            self.history_cleared.emit()


class SummaryDashboard(QWidget):
    def __init__(self, store, navigate, parent=None):
        super().__init__(parent)
        self.store = store
        self.stats = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        heading = QHBoxLayout()
        heading.addWidget(role(QLabel("Riepilogo attività"), "title"))
        heading.addStretch()
        history = QPushButton("Apri storico")
        history.clicked.connect(lambda: navigate("history"))
        heading.addWidget(history)
        layout.addLayout(heading)
        self.note = role(QLabel("Nessuna esecuzione registrata. Avvia un'attività dai tuoi preferiti."), "secondary")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("summaryBody")
        content = QVBoxLayout(body)
        content.setContentsMargins(0, 12, 0, 0)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.cards = {}
        for index, (key, title) in enumerate((("total", "Esecuzioni totali"), ("completed", "Completate"),
                                             ("failed", "Fallite"), ("rate", "Tasso di successo"))):
            card = QFrame()
            card.setStyleSheet("QFrame {background:#F5F5F8; border-radius:12px;}")
            box = QVBoxLayout(card)
            box.setContentsMargins(18, 16, 18, 16)
            box.addWidget(role(QLabel(title), "secondary"))
            value = role(QLabel("—"), "title")
            box.addWidget(value)
            self.cards[key] = value
            grid.addWidget(card, index // 2, index % 2)
        content.addLayout(grid)
        self.last = role(QLabel("Ultima attività: nessuna"), "body")
        self.last.setWordWrap(True)
        content.addWidget(self.last)
        content.addSpacing(12)
        content.addWidget(role(QLabel("Attività recenti"), "section"))
        self.recent = QTableWidget(0, 4)
        self.recent.setShowGrid(False)
        self.recent.verticalHeader().setDefaultSectionSize(36)
        self.recent.setHorizontalHeaderLabels(["Attività", "Data e ora", "Durata", "Esito"])
        self.recent.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2, 3):
            self.recent.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.recent.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recent.verticalHeader().hide()
        self.recent.setMinimumHeight(195)
        self.recent.setMaximumHeight(210)
        content.addWidget(self.recent)
        content.addSpacing(12)
        content.addWidget(role(QLabel("Attività più frequenti"), "section"))
        self.frequent = QVBoxLayout()
        content.addLayout(self.frequent)
        content.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        self.query = AsyncQuery(self)
        self.query.ready.connect(self.render)

    def refresh(self, *_):
        if self.isVisible():
            self.query.run(self.store.statistics)

    def render(self, result):
        if "error" in result:
            self.note.setText(result["error"])
            return
        self.stats = result["data"]
        counts, recent = self.stats["counts"], self.stats["recent"]
        total = sum(counts.values())
        completed = counts.get("completato", 0)
        finished = total - counts.get("in_esecuzione", 0)
        for key, value in {"total": str(total), "completed": str(completed),
                           "failed": str(counts.get("errore", 0)),
                           "rate": f"{completed / finished * 100:.0f}%" if finished else "—"}.items():
            self.cards[key].setText(value)
        self.note.setText("Nessuna esecuzione registrata. Avvia un'attività dai tuoi preferiti." if not total else
            f"Dati dello storico conservato · {counts.get('interrotto', 0)} interrotte · "
            f"{counts.get('in_esecuzione', 0)} in corso. Tasso: completate / concluse, incluse le interrotte.")
        self.last.setText(f"Ultima attività: {recent[0]['activity_name']} · {display_date(recent[0]['started_at'])}" if recent else
                          "Ultima attività: nessuna")
        self.recent.setRowCount(len(recent))
        for index, row in enumerate(recent):
            for column, value in enumerate((row["activity_name"], display_date(row["started_at"]),
                                            display_duration(row["duration"]), OUTCOMES[row["outcome"]])):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setIcon(activity_icon(row["activity_id"]))
                if column == 3:
                    item.setForeground(QColor("#B42332" if row["outcome"] == "errore" else
                                              Theme.SUCCESS if row["outcome"] == "completato" else Theme.MUTED))
                self.recent.setItem(index, column, item)
        while self.frequent.count():
            item = self.frequent.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self.stats["frequent"]:
            self.frequent.addWidget(role(QLabel("Le attività più usate appariranno dopo le prime esecuzioni."), "secondary"))
        for row in self.stats["frequent"]:
            self.frequent.addWidget(role(QLabel(f"{row['activity_name']} · {row['count']} esecuzioni"), "body"))
