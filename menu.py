# ─────────────────────────────────────────────────────────────
# REQUISITO: pip install PySide6
# ─────────────────────────────────────────────────────────────
import sys
import os
import re
import json
import shutil
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from updater import get_asset
from ui_theme import Theme, WORKSPACE_QSS, TERMINAL_QSS, role, set_tone, line_icon, activity_icon
from ui_widgets import ElidedLabel
from operational_preferences import Favorites
from execution_service import ExecutionService
from operations_views import HistoryPage, SummaryDashboard, AsyncQuery
from activity_status import StatusService
from workflow_service import WorkflowStore, WorkflowManager
from workflow_views import WorkflowPage as ManagedWorkflowPage

from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QScrollArea, QTextEdit,
    QSizePolicy, QStackedWidget, QGridLayout, QSpacerItem, QSplitter,
    QFileDialog, QMessageBox, QSplashScreen, QDialog,
    QDialogButtonBox, QLineEdit, QButtonGroup, QScroller
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QObject, QSize, QRect
from PySide6.QtGui import (
    QColor, QTextCharFormat, QTextCursor,
    QIcon, QPixmap, QPainter, QFont, QLinearGradient, QBrush
)


# ─────────────────────────────────────────────────────────────
# APP DIR  (funziona sia da .py che da .exe PyInstaller)
# ─────────────────────────────────────────────────────────────
def get_app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

BASE_DIR  = get_app_dir()
SCRIPTS_DIR = get_asset("scripts")
ICON_PATH = get_asset("logo.ico")

# ─────────────────────────────────────────────────────────────
# CONFIG  ─  lettura / scrittura config.json
# ─────────────────────────────────────────────────────────────
LEGACY_CONFIG_PATH = get_asset("config.json")
CONFIG_PATH = Path(os.environ.get("APPDATA", BASE_DIR)) / "MyWayTools" / "config.json"

# Struttura relativa attesa dentro la cartella SharePoint.
# Le chiavi corrispondono alle variabili PATH_* del vecchio codice.
_REL_PATHS = {
    "RAW_FILES"                 :"SCRIPT/00_RAW_FILE",
    # BUSINESS
    "ESTRAI_FILE_GARA"          : "BUSINESS/13_ESTRAI_FILE_GARA/ESTRAI_FILE_GARA.py",
    "ELABORA_CB"                : "BUSINESS/14_ELABORA_CB/main.py",
    "PERFORMANCE_MANAGEMENT_CRM": "BUSINESS/15_PERFORMANCE_MANAGEMENT_CRM/main.py",
    "FCST"                      : "BUSINESS/12_FCST_BUSINESS/crea_report_aggregato.py",
    "APPUNTAMENTI_SETTIMANA"    : "BUSINESS/02_(OLD)_APPUNTAMENTI_SETTIMANA/script/ESTRAI_APPUNTMANETI_SETTIMANA.py",
        #altri script
    "FORMATTA_GARA"             : "BUSINESS/09_ESTRAZIONE_ORDINI_API/AGGREGA_STORICO.py",
    "FORMATTA_OPPORTUNITA"      : "BUSINESS/10_ESTRAZIONE_OPP_API/AGGREGA_STORICO.py",
    "FORMATTA_APPUNTAMENTI"     : "BUSINESS/11_ESTRAZIONE_APP_API/AGGREGA_STORICO.py",
    "CHIUSURA_GARA"             : "BUSINESS/09_ESTRAZIONE_ORDINI_API/CHIUSURA_GARA.py",
        #campagne
    "DIVIDI_FILE_CAMPAGNE"      : "BUSINESS/CAMPAGNE/00_DIVIDI_FILE_CAMPAGNE/DIVIDI_CAMPAGNE.py",
    "AGGREGA_FILE_VENDITORI"    : "BUSINESS/CAMPAGNE/01_AGGREGA_FILE_VENDITORI/AGGREGA_FILE.py",
    "PRESA_IN_CARICO"           : "BUSINESS/CAMPAGNE/02_CONTROLLA_PRESA_IN_CARICO/PRESA_IN_CARICO.py",
    "REPORT_CAMPAGNE"           : "",
    # CONSUMER
    
    "REPORT_PEDONALITA"         : "CONSUMER/02_REPORT_PEDONALITA/script/CREA_REPORT_PEDONALITA.py",
    "CRUSCOTTO_TRACCIAMENTO"    : "CONSUMER/11_CRUSCOTTO_AGGREGATIVO/CRUSCOTTO_AGGREGATIVO.py",
    "CRUSCOTTO_GIORNALIERO"     : "CONSUMER/12_CRUSCOTTO_PISTA_CONSUMER/main.py",
    "REPORT_GIACENZE_SMARTPHONE": "CONSUMER/13_REPORT_GIACENZE/main.py",
    
        #altri script
    "FORMATTA_PEDONALITA"       : "CONSUMER/01_FORMATTA_PEDONALITA/script/FORMATTA_PEDONALITA.py",
    "FORMATTA_MAGAZZINO"        : "CONSUMER/03_FORMATTA_MAGAZZINO/FORMATTA_MAGAZZINO.py",

}

def _build_paths(sharepoint_root: Path, raw_files_path: Path | None = None) -> dict:
    """Costruisce i path del codice locale e dei dati su SharePoint."""
    paths = {
        key: SCRIPTS_DIR / rel
        for key, rel in _REL_PATHS.items()
        if key != "RAW_FILES"
    }
    paths["RAW_FILES"] = raw_files_path or (sharepoint_root / _REL_PATHS["RAW_FILES"])
    return paths

def carica_config() -> dict | None:
    """Legge config.json. Restituisce None se non esiste o è corrotto."""
    source = CONFIG_PATH if CONFIG_PATH.exists() else LEGACY_CONFIG_PATH
    if not source.exists():
        return None
    try:
        with open(source, encoding="utf-8") as f:
            data = json.load(f)
        root_value = data.get("sharepoint_root", "")
        raw_value = data.get("raw_files_path", "")
        root = Path(root_value) if root_value else None
        raw = Path(raw_value) if raw_value else None
        if not ((raw and raw.exists()) or (root and root.exists())):
            return None
        return data
    except Exception:
        return None

def salva_config(sharepoint_root: Path) -> None:
    """Salva config.json con la root SharePoint scelta dall'utente."""
    data = {"sharepoint_root": str(sharepoint_root)}
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def salva_cartella_raw(raw_files_path: Path, sharepoint_root: Path) -> None:
    """Salva la cartella RAW scelta dall'utente nel profilo locale."""
    data = {
        "sharepoint_root": str(sharepoint_root),
        "raw_files_path": str(raw_files_path),
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def prepara_env_locale(sharepoint_root: Path) -> Path | None:
    """Migra una sola volta il file segreto in APPDATA, fuori dall'installer."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    destinazione = Path(appdata) / "MyWayTools" / ".env"
    if destinazione.is_file():
        return destinazione

    candidati = (
        sharepoint_root / "SCRIPT" / ".env",
        SCRIPTS_DIR / ".env",
    )
    for sorgente in candidati:
        if sorgente.is_file():
            destinazione.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sorgente, destinazione)
            return destinazione
    return None


# ─────────────────────────────────────────────────────────────
# DIALOG DI PRIMA CONFIGURAZIONE
# ─────────────────────────────────────────────────────────────
class ConfigDialog(QDialog):
    """
    Mostrata all'avvio se config.json manca o la cartella non esiste.
    Chiede all'utente soltanto dove conservare i file RAW operativi.
    """
    def __init__(self, messaggio_extra: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurazione – MyWay Tools")
        self.setFixedWidth(540)
        self.setStyleSheet(f"background:{C_BG};")
        self.sharepoint_root: Path | None = None
        self.raw_files_path: Path | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 30, 30, 24)
        lay.setSpacing(14)

        # Icona + titolo
        titolo = QLabel("📁  Scegli la cartella RAW_FILES")
        titolo.setStyleSheet(f"font-size:18px; font-weight:bold; color:{C_TEXT_DARK};")
        lay.addWidget(titolo)

        if messaggio_extra:
            lbl_warn = QLabel(f"⚠️  {messaggio_extra}")
            lbl_warn.setStyleSheet(f"font-size:13px; color:{C_LOG_WARN}; background:#FFF8E7; "
                                    f"border:1px solid #FBBF24; border-radius:8px; padding:8px 12px;")
            lbl_warn.setWordWrap(True)
            lay.addWidget(lbl_warn)

        desc = QLabel(
            "Questa è la cartella in cui l'app leggerà e copierà i file da elaborare.\n"
            "Puoi scegliere una cartella locale oppure una cartella aziendale già disponibile sul PC.\n\n"
            "Potrai cambiarla in qualsiasi momento dalla Panoramica."
        )
        desc.setStyleSheet(f"font-size:13px; color:{C_TEXT_MID};")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Campo path + pulsante sfoglia
        row = QHBoxLayout()
        self.field = QLineEdit()
        self.field.setPlaceholderText("Percorso della cartella RAW_FILES…")
        self.field.setStyleSheet(f"""
            QLineEdit {{
                font-size:13px; padding:8px 10px;
                border:1px solid {C_BORDER}; border-radius:8px;
                background:white; color:{C_TEXT_DARK};
            }}
            QLineEdit:focus {{ border:1px solid {C_RED}; }}
        """)
        row.addWidget(self.field)

        btn_sfoglia = QPushButton("Sfoglia…")
        btn_sfoglia.setFixedHeight(36)
        btn_sfoglia.setStyleSheet(f"""
            QPushButton {{
                background:{C_RED}; color:white; border:none;
                border-radius:8px; font-size:13px; font-weight:bold;
                padding:0 16px;
            }}
            QPushButton:hover {{ background:{C_RED_HOVER}; }}
        """)
        btn_sfoglia.clicked.connect(self._sfoglia)
        row.addWidget(btn_sfoglia)
        lay.addLayout(row)

        # Hint cartella home
        hint = QLabel("💡 Scegli una cartella dedicata e facilmente riconoscibile.")
        hint.setStyleSheet(f"font-size:12px; color:{C_TEXT_LIGHT};")
        lay.addWidget(hint)

        # Bottoni OK / Annulla
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C_BORDER};")
        lay.addWidget(sep)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Salva e avvia")
        btns.button(QDialogButtonBox.Ok).setStyleSheet(f"""
            QPushButton {{
                background:{C_RED}; color:white; border:none;
                border-radius:8px; font-size:14px; font-weight:bold;
                padding:8px 20px;
            }}
            QPushButton:hover {{ background:{C_RED_HOVER}; }}
        """)
        btns.button(QDialogButtonBox.Cancel).setText("Esci")
        btns.accepted.connect(self._conferma)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _sfoglia(self):
        cartella = QFileDialog.getExistingDirectory(
            self, "Seleziona la cartella RAW_FILES", str(Path.home())
        )
        if cartella:
            self.field.setText(cartella)

    def _conferma(self):
        testo = self.field.text().strip()
        if not testo:
            QMessageBox.warning(self, "Percorso mancante", "Inserisci o seleziona una cartella.")
            return
        path = Path(testo)
        if not path.exists():
            QMessageBox.warning(self, "Cartella non trovata",
                                f"La cartella non esiste:\n{path}\n\n"
                                "Seleziona una cartella esistente.")
            return
        self.raw_files_path = path
        self.sharepoint_root = path.parent.parent if path.name.upper() == "00_RAW_FILE" else path.parent
        salva_cartella_raw(path, self.sharepoint_root)
        self.accept()


# ─────────────────────────────────────────────────────────────
# PALETTE COLORI
# ─────────────────────────────────────────────────────────────
C_BG         = "#F4F6F9"
C_PANEL      = "#FFFFFF"
C_SIDEBAR    = "#111827"
C_RED        = "#E30613"
C_RED_HOVER  = "#C9000C"
C_RED_LIGHT  = "#FDECEE"
C_FASTWEB    = "#FFD400"
C_FASTWEB_HOVER = "#F2C900"
C_FASTWEB_LIGHT = "#FFF7CC"
C_TEXT_DARK  = "#111827"
C_TEXT_MID   = "#4B5563"
C_TEXT_LIGHT = "#7B8494"
C_BORDER     = "#E3E7ED"

C_LOG_BG   = "#1A1A1A"
C_LOG_TEXT = "#E0E0E0"
C_LOG_OK   = "#4ADE80"
C_LOG_ERR  = "#FF6B6B"
C_LOG_INFO = "#60A5FA"
C_LOG_WARN = "#FBBF24"


# ─────────────────────────────────────────────────────────────
# ICONA APP
# ─────────────────────────────────────────────────────────────
def carica_icona() -> QIcon:
    if ICON_PATH.exists():
        return QIcon(str(ICON_PATH))
    px = QPixmap(64, 64)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor(C_RED)))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, 64, 64, 14, 14)
    p.setPen(QColor("white"))
    p.setFont(QFont("Arial", 32, QFont.Bold))
    p.drawText(px.rect(), Qt.AlignCenter, "M")
    p.end()
    return QIcon(px)


# ─────────────────────────────────────────────────────────────
# SPLASH SCREEN
# ─────────────────────────────────────────────────────────────
class SplashScreen(QSplashScreen):
    def __init__(self):
        px = QPixmap(480, 280)
        px.fill(Qt.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, 480, 280, 18, 18)
        p.setBrush(QBrush(QColor(C_RED)))
        p.drawRoundedRect(0, 0, 480, 8, 4, 4)
        p.drawRect(0, 4, 480, 4)
        if ICON_PATH.exists():
            logo = QPixmap(str(ICON_PATH)).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(208, 42, logo)
        else:
            p.setBrush(QBrush(QColor(C_RED)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(208, 42, 64, 64)
            p.setPen(QColor("white"))
            p.setFont(QFont("Arial", 30, QFont.Bold))
            p.drawText(208, 42, 64, 64, Qt.AlignCenter, "M")
        p.setPen(QColor(C_TEXT_DARK))
        p.setFont(QFont("Arial", 26, QFont.Bold))
        p.drawText(0, 124, 480, 40, Qt.AlignCenter, "MyWay Tools")
        p.setPen(QColor(C_TEXT_LIGHT))
        p.setFont(QFont("Arial", 13))
        p.drawText(0, 166, 480, 28, Qt.AlignCenter, "Piattaforma di automazione ETL")
        p.setPen(QColor(C_BORDER))
        p.drawLine(40, 210, 440, 210)
        p.setPen(QColor(C_TEXT_LIGHT))
        p.setFont(QFont("Arial", 11))
        p.drawText(0, 220, 480, 24, Qt.AlignCenter, "Caricamento in corso...")
        p.setFont(QFont("Arial", 10))
        p.drawText(0, 252, 480, 20, Qt.AlignCenter, f"© {datetime.now().year} MyWay")
        p.end()
        super().__init__(px)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)


# ─────────────────────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────────────────────
def rimuovi_ansi(text):
    return re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]').sub('', text)

def check_file_presenti(cartella: Path, numero_atteso=3):
    try:
        files = [f for f in cartella.glob("*") if f.is_file()]
        return len(files), numero_atteso
    except Exception:
        return 0, numero_atteso

def check_file_per_nome(cartella: Path, nome_atteso: str):
    try:
        matches = [f for f in cartella.glob(nome_atteso) if f.is_file()]
        return len(matches) > 0, matches[0].name if matches else None
    except Exception:
        return False, None

def colore_riga(line):
    l = line.lower()
    if any(k in l for k in ["✅", "ok", "success", "completato", "done"]):
        return C_LOG_OK
    if any(k in l for k in ["❌", "error", "errore", "exception", "traceback", "failed"]):
        return C_LOG_ERR
    if any(k in l for k in ["⚠️", "warning", "attenzione"]):
        return C_LOG_WARN
    if any(k in l for k in ["info", "avvio", "→", "caricamento"]):
        return C_LOG_INFO
    return C_LOG_TEXT

def formatta_dimensione(byte):
    if byte < 1024:
        return f"{byte} B"
    elif byte < 1024 ** 2:
        return f"{byte / 1024:.0f} KB"
    else:
        return f"{byte / 1024 ** 2:.1f} MB"


# ─────────────────────────────────────────────────────────────
# SEGNALI GLOBALI
# ─────────────────────────────────────────────────────────────
class GlobalSignals(QObject):
    script_avviato   = Signal()
    script_terminato = Signal()

global_signals = GlobalSignals()


# ─────────────────────────────────────────────────────────────
# SIGNAL BRIDGE log (thread → GUI)
# ─────────────────────────────────────────────────────────────
class LogSignals(QObject):
    append = Signal(str, str)

class ScriptCardSignals(QObject):
    script_finished = Signal(bool)


class RemoteCheckSignals(QObject):
    finished = Signal(bool, str)


# ─────────────────────────────────────────────────────────────
# TERMINALE WIDGET
# ─────────────────────────────────────────────────────────────
class TerminaleWidget(QFrame):
    collapsed_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._expanded_height = 210
        self.setObjectName("terminal")
        self.setMinimumHeight(Theme.TERMINAL_HEADER)
        self.setStyleSheet(TERMINAL_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("terminalHeader")
        header.setFixedHeight(Theme.TERMINAL_HEADER)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 12, 0)
        h_lay.addWidget(QLabel("Terminale"))
        self.state = QLabel("Pronto")
        h_lay.addWidget(self.state)
        h_lay.addStretch()

        self.btn_clear = QPushButton("Pulisci")
        self.btn_clear.clicked.connect(self.pulisci)
        h_lay.addWidget(self.btn_clear)
        self.btn_toggle = QPushButton("Nascondi")
        self.btn_toggle.clicked.connect(self._toggle)
        h_lay.addWidget(self.btn_toggle)
        layout.addWidget(header)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setAccessibleName("Log operativi")
        layout.addWidget(self.log)

        self.signals = LogSignals(self)
        self.signals.append.connect(self._append_colored)
        global_signals.script_avviato.connect(self.script_started)
        global_signals.script_terminato.connect(self.script_finished)
        self._write("Pronto. Avvia uno script per vedere l'output qui.\n", C_LOG_INFO)

    @Slot(str, str)
    def _append_colored(self, testo, colore):
        scrollbar = self.log.verticalScrollBar()
        follow = scrollbar.value() >= scrollbar.maximum() - 4
        cursor = QTextCursor(self.log.document())
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colore))
        cursor.insertText(testo, fmt)
        if follow:
            scrollbar.setValue(scrollbar.maximum())

    def _write(self, testo, colore):
        self._append_colored(testo, colore)

    def write_safe(self, testo, colore):
        self.signals.append.emit(testo, colore)

    def pulisci(self):
        self.log.clear()

    @Slot()
    def script_started(self):
        self.state.setText("In esecuzione")
        if getattr(getattr(self, "execution_service", None), "workflow_owner", None) is None:
            self.set_collapsed(False)

    @Slot()
    def script_finished(self):
        self.state.setText("Pronto")

    def _toggle(self, checked=False):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed):
        splitter = self.parentWidget()
        if collapsed and not self._collapsed and isinstance(splitter, QSplitter):
            self._expanded_height = max(140, splitter.sizes()[-1])
        self._collapsed = collapsed
        self.log.setVisible(not collapsed)
        self.setMinimumHeight(Theme.TERMINAL_HEADER if collapsed else 140)
        self.setMaximumHeight(Theme.TERMINAL_HEADER if collapsed else 16777215)
        self.btn_toggle.setText("Mostra" if collapsed else "Nascondi")
        if isinstance(splitter, QSplitter):
            total = max(sum(splitter.sizes()), splitter.height() - splitter.handleWidth())
            height = Theme.TERMINAL_HEADER if collapsed else min(self._expanded_height, max(140, total // 2))
            splitter.setSizes([max(1, total - height), height])
        self.collapsed_changed.emit(collapsed)


# ─────────────────────────────────────────────────────────────
# PYTHON FINDER
# ─────────────────────────────────────────────────────────────
def _trova_python() -> str:
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent
    runtime_python = app_dir / "_runtime" / "python.exe"
    if runtime_python.exists():
        return str(runtime_python)
    import shutil
    for nome in ("python", "python3"):
        trovato = shutil.which(nome)
        if trovato:
            return trovato
    return "python"


# ─────────────────────────────────────────────────────────────
# LANCIA SCRIPT
# ─────────────────────────────────────────────────────────────
def lancia_script(nome_script, terminale: TerminaleWidget, on_finished=None):
    """Compatibility entrypoint shared by all launchers."""
    service = getattr(terminale, "execution_service", None)
    if service is None:
        service = ExecutionService(terminale, _trova_python)
        terminale.execution_service = service
        service.started.connect(lambda activity: global_signals.script_avviato.emit())
        service.finished.connect(lambda result: global_signals.script_terminato.emit())
    return service.launch_path(nome_script, on_finished)


CARD_HEIGHT        = 274
CARD_HEIGHT_STATUS = 274

class ScriptCard(QFrame):
    def __init__(self, icona, titolo, descrizione, script, terminale,
                 cartella: Path = None, nome_file=None, nomi_file=None, parent=None):
        super().__init__(parent)
        self.script    = script
        self.terminale = terminale
        self.cartella  = Path(cartella) if cartella and str(cartella).strip() else None
        self.nome_file = nome_file
        self.nomi_file = nomi_file
        self._in_esecuzione = False
        self._available = bool(script) and Path(script).is_file()

        self.setStyleSheet(f"""
            ScriptCard {{ background:{C_PANEL}; border-radius:12px; border:1px solid {C_BORDER}; }}
            ScriptCard:hover {{ background:#FFFFFF; border:1px solid #F1A1A7; }}
        """)
        self.setFixedHeight(CARD_HEIGHT_STATUS if cartella else CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(180)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(5)

        top = QHBoxLayout()
        lbl_icona = QLabel(icona)
        lbl_icona.setStyleSheet(f"font-size:27px; color:{C_RED}; background:transparent; border:none;")
        top.addWidget(lbl_icona)
        num = titolo.split(".")[0].strip()
        lbl_num = QLabel(f"  {num:>02}")
        lbl_num.setStyleSheet(f"background:{C_FASTWEB}; color:#111827; border-radius:6px; font-size:13px; font-weight:bold; padding:3px 9px; border:none;")
        lbl_num.setFixedHeight(28)
        top.addWidget(lbl_num)
        top.addStretch()
        lay.addLayout(top)

        titolo_pulito = titolo.split(".", 1)[-1].strip()
        lbl_titolo = QLabel(titolo_pulito)
        lbl_titolo.setStyleSheet(f"font-size:18px; font-weight:bold; color:{C_TEXT_DARK}; background:transparent; border:none;")
        lbl_titolo.setWordWrap(True)
        lay.addWidget(lbl_titolo)

        lbl_desc = QLabel(descrizione)
        lbl_desc.setStyleSheet(f"font-size:14px; color:{C_TEXT_LIGHT}; background:transparent; border:none;")
        lbl_desc.setWordWrap(True)
        lay.addWidget(lbl_desc)

        lay.addStretch(1)

        if self.cartella:
            self.status_frame = QFrame()
            self.status_frame.setFixedHeight(40)
            self.status_frame.setStyleSheet(f"QFrame {{ background:#F5F5F5; border-radius:8px; border:1px solid {C_BORDER}; }}")
            sf_lay = QHBoxLayout(self.status_frame)
            sf_lay.setContentsMargins(10, 6, 10, 6)
            self.status_label = QLabel("⏳ Controllo...")
            self.status_label.setStyleSheet(f"font-size:13px; font-weight:bold; color:{C_TEXT_MID}; background:transparent; border:none;")
            sf_lay.addWidget(self.status_label)
            lay.addWidget(self.status_frame)
        else:
            placeholder = QFrame()
            placeholder.setFixedHeight(34)
            placeholder.setStyleSheet("background:transparent; border:none;")
            lay.addWidget(placeholder)

        self.btn_avvia = QPushButton("Avvia  →")
        self.btn_avvia.setStyleSheet(f"""
            QPushButton {{ background:{C_RED}; color:white; border:none; border-radius:7px; font-size:14px; font-weight:bold; padding:7px 16px; }}
            QPushButton:hover {{ background:{C_RED_HOVER}; }}
            QPushButton:disabled {{ background:#CCCCCC; color:#888888; }}
        """)
        self.btn_avvia.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_avvia.setFixedWidth(150)
        self.btn_avvia.setFixedHeight(38)
        self.btn_avvia.clicked.connect(self._on_avvia_clicked)
        lay.addWidget(self.btn_avvia, alignment=Qt.AlignLeft)
        if not self._available:
            self.btn_avvia.setEnabled(False)
            self.btn_avvia.setText("In sviluppo")

        if self.cartella:
            self.timer_stato = QTimer(self)
            self.timer_stato.timeout.connect(self._aggiorna_stato)
            self.timer_stato.start(5000)
            self._aggiorna_stato()

        self._signals = ScriptCardSignals()
        self._signals.script_finished.connect(self._on_script_finished)
        global_signals.script_avviato.connect(self._on_qualsiasi_script_avviato)
        global_signals.script_terminato.connect(self._on_qualsiasi_script_terminato)

    def _on_avvia_clicked(self):
        if not self._available:
            return
        scroll = self._trova_scroll()
        pos = scroll.verticalScrollBar().value() if scroll else 0
        self._in_esecuzione = True
        self.btn_avvia.setEnabled(False)
        self.btn_avvia.setText("In esecuzione...")
        if scroll:
            QTimer.singleShot(0, lambda: scroll.verticalScrollBar().setValue(pos))
        lancia_script(self.script, self.terminale, on_finished=self._signals.script_finished.emit)

    def _trova_scroll(self):
        w = self.parent()
        while w:
            if isinstance(w, QScrollArea): return w
            w = w.parent()
        return None

    def _on_script_finished(self, successo: bool):
        self._in_esecuzione = False
        self.btn_avvia.setText("OK Avvia  →" if successo else "ERR Avvia  →")
        QTimer.singleShot(1500, lambda: self.btn_avvia.setText("Avvia  →"))

    def _on_qualsiasi_script_avviato(self):
        if not self._in_esecuzione:
            scroll = self._trova_scroll()
            pos = scroll.verticalScrollBar().value() if scroll else 0
            self.btn_avvia.setEnabled(False)
            self.btn_avvia.setText("Attendere...")
            if scroll:
                QTimer.singleShot(0, lambda: scroll.verticalScrollBar().setValue(pos))

    def _on_qualsiasi_script_terminato(self):
        if not self._in_esecuzione:
            if not self._available:
                self.btn_avvia.setEnabled(False)
                self.btn_avvia.setText("In sviluppo")
                return
            self.btn_avvia.setText("Avvia  →")
            if self.cartella and self.cartella.is_dir():
                self._aggiorna_stato()
            else:
                self.btn_avvia.setEnabled(True)

    def _aggiorna_stato(self):
        if self._in_esecuzione: return
        if not self.cartella or not self.cartella.is_dir():
            self.btn_avvia.setEnabled(True)
            return
        try:
            if self.nomi_file:
                mancanti, trovati = [], []
                for filename in self.nomi_file:
                    ok, match = check_file_per_nome(self.cartella, filename)
                    (trovati if ok else mancanti).append(match if ok else filename)
                if not mancanti:
                    self.status_label.setText("✅ Tutti i file presenti")
                    self.status_label.setStyleSheet(f"font-size:13px; font-weight:bold; color:{C_LOG_OK}; background:transparent; border:none;")
                    self.btn_avvia.setEnabled(True)
                else:
                    self.status_label.setText(f"❌ Mancano: {', '.join(mancanti)}")
                    self.status_label.setStyleSheet(f"font-size:13px; font-weight:bold; color:{C_LOG_ERR}; background:transparent; border:none;")
                    self.btn_avvia.setEnabled(False)
                return
            if self.nome_file:
                trovato, match = check_file_per_nome(self.cartella, self.nome_file)
                if trovato:
                    self.status_label.setText(f"✅ {match}")
                    self.status_label.setStyleSheet(f"font-size:13px; font-weight:bold; color:{C_LOG_OK}; background:transparent; border:none;")
                    self.btn_avvia.setEnabled(True)
                else:
                    self.status_label.setText(f"❌ Manca file '{self.nome_file}'")
                    self.status_label.setStyleSheet(f"font-size:13px; font-weight:bold; color:{C_LOG_ERR}; background:transparent; border:none;")
                    self.btn_avvia.setEnabled(False)
                return
            trovati, attesi = check_file_presenti(self.cartella, 3)
            if trovati >= attesi:
                self.status_label.setText(f"✅ Pronto  ({trovati}/{attesi} file)")
                self.status_label.setStyleSheet(f"font-size:13px; font-weight:bold; color:{C_LOG_OK}; background:transparent; border:none;")
                self.btn_avvia.setEnabled(True)
            else:
                self.status_label.setText(f"❌ Mancano file  ({trovati}/{attesi})")
                self.status_label.setStyleSheet(f"font-size:13px; font-weight:bold; color:{C_LOG_ERR}; background:transparent; border:none;")
                self.btn_avvia.setEnabled(False)
        except Exception:
            self.status_label.setText("❌ Errore controllo")
            self.status_label.setStyleSheet(f"font-size:13px; font-weight:bold; color:{C_LOG_ERR}; background:transparent; border:none;")
            self.btn_avvia.setEnabled(False)


# ─────────────────────────────────────────────────────────────
# RAW FILES WIDGET
# ─────────────────────────────────────────────────────────────
class RawFilesWidget(QFrame):
    _ESCLUDI = {".DS_Store", "Thumbs.db", "desktop.ini"}

    def __init__(self, cartella: Path, on_folder_changed=None, parent=None):
        super().__init__(parent)
        self.cartella = Path(cartella)
        self.on_folder_changed = on_folder_changed
        self.setObjectName("rawFiles")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(190)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(11)

        header_row = QHBoxLayout()
        icona = QLabel()
        icona.setPixmap(line_icon("files").pixmap(QSize(24, 24)))
        header_row.addWidget(icona)
        lbl_titolo = role(QLabel("File RAW"), "section")
        header_row.addWidget(lbl_titolo)
        header_row.addStretch()
        self.lbl_count = QLabel("0 file")
        self.lbl_count.setObjectName("fileCount")
        header_row.addWidget(self.lbl_count)
        btn_cartella = QPushButton("Cambia cartella")
        btn_cartella.setCursor(Qt.PointingHandCursor)
        btn_cartella.clicked.connect(self._scegli_cartella)
        header_row.addWidget(btn_cartella)
        btn_carica = role(QPushButton("Carica file"), "primary")
        btn_carica.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_carica.clicked.connect(self._carica_file)
        header_row.addWidget(btn_carica)
        outer.addLayout(header_row)

        self.lbl_percorso = role(ElidedLabel(), "secondary")
        self.lbl_percorso.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_percorso.setToolTip(str(self.cartella))
        outer.addWidget(self.lbl_percorso)

        sep = role(QFrame(), "separator")
        sep.setFixedHeight(1)
        outer.addWidget(sep)

        self.lista_frame = QFrame()
        self.lista_layout = QVBoxLayout(self.lista_frame)
        self.lista_layout.setContentsMargins(0, 0, 0, 0)
        self.lista_layout.setSpacing(4)
        outer.addWidget(self.lista_frame)

        self.lbl_vuoto = role(QLabel("Nessun file presente. Carica i file RAW da processare."), "secondary")
        self.lbl_vuoto.setWordWrap(True)
        self.lbl_vuoto.setContentsMargins(0, 12, 0, 12)
        self.lbl_vuoto.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.lbl_vuoto)

        hint = QLabel("Trascina qui i file oppure usa il pulsante Carica file")
        hint.setObjectName("dropHint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        outer.addWidget(hint)

        self.setAcceptDrops(True)
        self._file_query = AsyncQuery(self)
        self._file_query.ready.connect(self._render_files)
        self._timer = QTimer(self)
        self._timer.timeout.connect(lambda: self._aggiorna_lista() if self.isVisible() else None)
        self._timer.start(30000)
        self._aggiorna_lista()

    def _scegli_cartella(self):
        scelta = QFileDialog.getExistingDirectory(
            self, "Scegli la cartella RAW_FILES", str(self.cartella.parent))
        if not scelta:
            return
        self.cartella = Path(scelta)
        self.lbl_percorso.setToolTip(str(self.cartella))
        self._aggiorna_lista(force=True)
        if self.on_folder_changed:
            self.on_folder_changed(self.cartella)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set_drag_over(True)

    def dragLeaveEvent(self, e):
        self._set_drag_over(False)

    def dropEvent(self, e):
        self._set_drag_over(False)
        if e.mimeData().hasUrls():
            self._copia_files([Path(u.toLocalFile()) for u in e.mimeData().urls()])

    def _set_drag_over(self, active):
        self.setProperty("dragOver", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _leggi_files(self):
        if not self.cartella.exists(): return []
        return sorted(
            (f for f in self.cartella.glob("*")
             if f.is_file() and f.name not in self._ESCLUDI and not f.name.startswith(".")),
            key=lambda f: f.name.lower()
        )

    def _aggiorna_lista(self, force=False):
        folder = self.cartella
        def read_files():
            files = sorted((f for f in folder.iterdir() if f.is_file() and f.name not in self._ESCLUDI
                            and not f.name.startswith(".")), key=lambda f: f.name.lower())
            return folder, [(file, file.stat().st_size) for file in files], force
        self._file_query.run(read_files)

    def _render_files(self, result):
        if "error" in result:
            self.lbl_count.setText("Errore di verifica")
            self.lbl_vuoto.setText("Impossibile leggere la cartella RAW. Controlla disponibilità e permessi.")
            self.lbl_vuoto.show()
            self.lista_frame.hide()
            return
        folder, entries, force = result["data"]
        if folder != self.cartella:
            return
        files = [file for file, size in entries]
        self.lbl_vuoto.setText("Nessun file presente. Carica i file RAW da processare.")
        self.lbl_percorso.setText(f"Cartella attiva:  {self.cartella}")
        self.lbl_count.setText(f"{len(files)} file" if len(files) != 1 else "1 file")
        self.lbl_vuoto.setVisible(len(files) == 0)
        self.lista_frame.setVisible(len(files) > 0)
        nomi_attuali = {
            self.lista_layout.itemAt(i).widget().property("nome_file")
            for i in range(self.lista_layout.count())
            if self.lista_layout.itemAt(i).widget()
        }
        if not force and nomi_attuali == {f.name for f in files}: return
        while self.lista_layout.count():
            item = self.lista_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for fpath, size in entries:
            self.lista_layout.addWidget(self._crea_riga(fpath, size))
        self.lbl_vuoto.setVisible(len(files) == 0)
        self.lista_frame.setVisible(len(files) > 0)

    def _crea_riga(self, fpath: Path, size=None) -> QFrame:
        riga = QFrame()
        riga.setProperty("nome_file", fpath.name)
        riga.setFixedHeight(42)
        riga.setObjectName("fileRow")
        lay = QHBoxLayout(riga)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(10)
        lbl_ico = QLabel()
        lbl_ico.setPixmap(line_icon("document").pixmap(QSize(18, 18)))
        lbl_ico.setFixedWidth(22)
        lay.addWidget(lbl_ico)
        lbl_nome = ElidedLabel(fpath.name)
        lay.addWidget(lbl_nome)
        size_str = formatta_dimensione(size) if size is not None else "—"
        lbl_size = role(QLabel(size_str), "secondary")
        lbl_size.setFixedWidth(60)
        lbl_size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(lbl_size)
        btn_del = QPushButton()
        btn_del.setIcon(line_icon("trash"))
        btn_del.setFixedSize(32, 32)
        btn_del.setProperty("role", "iconButton")
        btn_del.setToolTip(f"Elimina {fpath.name}")
        btn_del.setAccessibleName(f"Elimina {fpath.name}")
        btn_del.clicked.connect(lambda checked=False, p=fpath: self._elimina_file(p))
        lay.addWidget(btn_del)
        return riga

    def _carica_file(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Seleziona file", str(Path.home()), "Tutti i file (*.*)")
        if files: self._copia_files([Path(f) for f in files])

    def _copia_files(self, sorgenti: list):
        if not self.cartella.exists():
            try: self.cartella.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile creare la cartella:\n{e}")
                return
        for src in sorgenti:
            if not src.is_file(): continue
            dest = self.cartella / src.name
            if dest.exists():
                r = QMessageBox.question(self, "File già presente", f"Sovrascrivere «{src.name}»?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if r != QMessageBox.Yes: continue
            try:
                import shutil; shutil.copy2(src, dest)
            except Exception as e:
                QMessageBox.warning(self, "Errore copia", f"Impossibile copiare {src.name}:\n{e}")
        self._aggiorna_lista()

    def _elimina_file(self, fpath: Path):
        r = QMessageBox.question(self, "Elimina file", f"Eliminare «{fpath.name}»?",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r == QMessageBox.Yes:
            try: fpath.unlink(); self._aggiorna_lista()
            except Exception as e: QMessageBox.warning(self, "Errore", str(e))


# ─────────────────────────────────────────────────────────────
# SECTION LABEL
# ─────────────────────────────────────────────────────────────
def crea_section_label(testo):
    frame = QFrame()
    frame.setStyleSheet("background:transparent; border:none;")
    lay = QHBoxLayout(frame)
    lay.setContentsMargins(2, 16, 2, 9)
    lay.setSpacing(0)
    bar = QFrame()
    bar.setFixedSize(4, 20)
    bar.setStyleSheet(f"background:{C_FASTWEB}; border:none; border-radius:2px;")
    lay.addWidget(bar)
    lay.addSpacing(10)
    lbl = QLabel(testo)
    lbl.setStyleSheet(f"color:{C_TEXT_DARK}; font-size:16px; font-weight:bold; background:transparent; border:none;")
    lay.addWidget(lbl)
    lay.addStretch()
    return frame


# ─────────────────────────────────────────────────────────────
# NAV BUTTON
# ─────────────────────────────────────────────────────────────
class NavButton(QFrame):
    def __init__(self, testo, icona, comando, attivo=False, sottovoci=None, parent=None):
        super().__init__(parent)
        self.comando = comando
        self.attivo  = attivo
        bg     = C_FASTWEB_LIGHT if attivo else "transparent"
        border = "border:none; border-radius:8px;"
        self.setStyleSheet(f"QFrame {{ background:{bg}; {border} }}")
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        header = QFrame()
        header_bg = C_FASTWEB if attivo else "transparent"
        header.setStyleSheet(f"background:{header_bg}; border:none; border-radius:8px;")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(12, 8, 12, 8)
        h_lay.setSpacing(0)
        fg   = "#111827" if attivo else "#C7CDD7"
        peso = "bold" if attivo else "normal"
        lbl  = QLabel(f"  {icona}  {testo}")
        lbl.setStyleSheet(f"color:{fg}; font-size:16px; font-weight:{peso}; background:transparent; border:none;")
        lbl.setCursor(Qt.PointingHandCursor)
        h_lay.addWidget(lbl)
        h_lay.addStretch()
        lay.addWidget(header)
        if attivo and sottovoci:
            content = QFrame()
            content.setStyleSheet("background:transparent; border:none;")
            c_lay = QVBoxLayout(content)
            c_lay.setContentsMargins(14, 2, 14, 10)
            c_lay.setSpacing(4)
            linea_sep = QFrame()
            linea_sep.setFixedHeight(1)
            linea_sep.setStyleSheet(f"background:{C_FASTWEB_HOVER}; border:none;")
            c_lay.addWidget(linea_sep)
            for sezione, voci in sottovoci:
                s_frame = QFrame()
                s_frame.setStyleSheet("background:transparent; border:none;")
                s_lay = QHBoxLayout(s_frame)
                s_lay.setContentsMargins(2, 7, 0, 3)
                s_lay.setSpacing(8)
                bar = QFrame()
                bar.setFixedSize(3, 14)
                bar.setStyleSheet(f"background:{C_FASTWEB}; border:none;")
                s_lay.addWidget(bar)
                lbl_s = QLabel(sezione)
                lbl_s.setStyleSheet("color:#111827; font-size:14px; font-weight:bold; background:transparent; border:none;")
                s_lay.addWidget(lbl_s)
                s_lay.addStretch()
                c_lay.addWidget(s_frame)
                for voce in voci:
                    v_lbl = QLabel(f"· {voce}")
                    v_lbl.setStyleSheet("color:#374151; font-size:14px; padding:3px 0 3px 22px; background:transparent; border:none;")
                    v_lbl.setWordWrap(True)
                    c_lay.addWidget(v_lbl)
            lay.addWidget(content)
        for w in self.findChildren(QWidget):
            w.mousePressEvent = lambda e, c=comando: c()
        self.mousePressEvent = lambda e: comando()


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
class Sidebar(QFrame):
    def __init__(self, pagina_attiva, nav_callback, sharepoint_root: Path, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet(f"QFrame {{ background:{C_SIDEBAR}; border:none; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        barra = QFrame()
        barra.setFixedHeight(5)
        barra.setStyleSheet(f"background:{C_FASTWEB}; border:none;")
        lay.addWidget(barra)

        logo_frame = QFrame()
        logo_frame.setStyleSheet("background:transparent; border:none;")
        logo_lay = QHBoxLayout(logo_frame)
        logo_lay.setContentsMargins(24, 25, 24, 18)
        logo_lay.setSpacing(0)
        if ICON_PATH.exists():
            px_logo = QPixmap(str(ICON_PATH)).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl_logo = QLabel()
            lbl_logo.setPixmap(px_logo)
            lbl_logo.setStyleSheet("background:transparent; border:none;")
            logo_lay.addWidget(lbl_logo)
        else:
            lbl_dot = QLabel("●")
            lbl_dot.setStyleSheet(f"color:{C_RED}; font-size:28px; font-weight:bold; background:transparent;")
            logo_lay.addWidget(lbl_dot)
        lbl_title = QLabel(" INDICE")
        lbl_title.setStyleSheet("color:#FFFFFF; font-size:20px; font-weight:bold; background:transparent;")
        logo_lay.addWidget(lbl_title)
        logo_lay.addStretch()
        lay.addWidget(logo_frame)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#273244; border:none; margin-left:20px; margin-right:20px;")
        lay.addWidget(sep)
        lay.addSpacing(10)

        lbl_nav = QLabel("NAVIGAZIONE")
        lbl_nav.setStyleSheet("color:#7F8999; font-size:10px; font-weight:bold; background:transparent; border:none;")
        lbl_nav.setContentsMargins(28, 0, 0, 8)
        lay.addWidget(lbl_nav)

        home_sottovoci        = [] if pagina_attiva == "main" else None
        giornalieri_sottovoci = [
            ("Business",          ["Estrai file gara", "FCST", "Appuntamenti", "Performance Management CRM"]),
            ("Consumer / Negozi", ["Formatta pedonalità", "Cruscotto Tracciamento", "Cruscotto Giornaliero"]),
        ] if pagina_attiva == "giornalieri" else None
        campagne_sottovoci    = [
            ("Campagne", ["Divisione per aente", "Riaggrega file Campagne", "Presa in carico cliente", "Report Campagne(⚒️)"]),
        ] if pagina_attiva == "campagne" else None
        altro_sottovoci       = [
            ("Business", ["Formatta file Gara", "Formatta file appuntamenti", "Formatta file opportunità", "Chiusura gara"]),
            ("File negozi", ["Report pedonalità", "Formatta magazzino", "Formatta performance(⚒️)"])
        ] if pagina_attiva == "altri script" else None

        nav_items = [
            ("Home",          "🏠", "main",          home_sottovoci),
            ("Giornalieri",   "🔄", "giornalieri",   giornalieri_sottovoci),
            ("Altri script",  "🖋️", "altri script",  altro_sottovoci),
            ("Campagne (⚒️ in corso)", "📣", "campagne",     campagne_sottovoci),
        ]
        for testo, icona, nome, sottovoci in nav_items:
            btn = NavButton(testo, icona, lambda n=nome: nav_callback(n),
                            attivo=(pagina_attiva == nome), sottovoci=sottovoci)
            frame = QFrame()
            frame.setStyleSheet("background:transparent; border:none;")
            f_lay = QVBoxLayout(frame)
            f_lay.setContentsMargins(14, 2, 14, 2)
            f_lay.addWidget(btn)
            lay.addWidget(frame)

        lay.addStretch()

        # ── Footer: path SharePoint + bottone "Cambia" ────────
        bottom = QFrame()
        bottom.setStyleSheet("background:transparent; border:none;")
        b_lay = QVBoxLayout(bottom)
        b_lay.setContentsMargins(16, 0, 16, 20)
        b_lay.setSpacing(8)

        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background:#273244;")
        b_lay.addWidget(sep2)

        # Path SharePoint corrente
        lbl_sp = QLabel("📂  SharePoint:")
        lbl_sp.setStyleSheet("color:#7F8999; font-size:10px; background:transparent; border:none;")
        b_lay.addWidget(lbl_sp)

        lbl_sp_path = QLabel(str(sharepoint_root))
        lbl_sp_path.setStyleSheet("color:#B5BDC9; font-size:10px; background:transparent; border:none;")
        lbl_sp_path.setWordWrap(True)
        b_lay.addWidget(lbl_sp_path)

        btn_cambia = QPushButton("🔧  Cambia cartella SharePoint")
        btn_cambia.setStyleSheet(f"""
            QPushButton {{ background:#1F2937; color:#E5E7EB; border:1px solid #374151;
                border-radius:8px; font-size:13px; padding:6px; text-align:left; }}
            QPushButton:hover {{ background:#293548; color:white; }}
        """)
        btn_cambia.clicked.connect(nav_callback.__self__._cambia_sharepoint
                                   if hasattr(nav_callback, '__self__') else lambda: None)
        # usa un segnale tramite closure per evitare dipendenza circolare
        btn_cambia._nav_callback = nav_callback
        btn_cambia.clicked.disconnect()
        btn_cambia.clicked.connect(lambda: nav_callback("_cambia_sharepoint"))
        b_lay.addWidget(btn_cambia)

        sep3 = QFrame()
        sep3.setFixedHeight(1)
        sep3.setStyleSheet("background:#273244;")
        b_lay.addWidget(sep3)

        btn_esci = QPushButton("Esci")
        btn_esci.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:#C7CDD7; border:none; border-radius:8px;
                font-size:14px; padding:8px; text-align:left; }}
            QPushButton:hover {{ background:#1F2937; color:white; }}
        """)
        btn_esci.clicked.connect(QApplication.quit)
        b_lay.addWidget(btn_esci)
        lay.addWidget(bottom)


# ─────────────────────────────────────────────────────────────
# GLOBAL HEADER
# ─────────────────────────────────────────────────────────────
class GlobalHeader(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(88)
        self.setStyleSheet(f"background:{C_BG}; border:none;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(30, 8, 30, 8)
        left = QFrame()
        left.setStyleSheet("background:transparent; border:none;")
        l_lay = QVBoxLayout(left)
        l_lay.setContentsMargins(0, 0, 0, 0)
        l_lay.setSpacing(1)
        self.lbl_breadcrumb  = QLabel("Home")
        self.lbl_breadcrumb.setStyleSheet(f"color:{C_RED}; font-size:11px; font-weight:bold;")
        self.lbl_titolo      = QLabel("MyWay Tools")
        self.lbl_titolo.setStyleSheet(f"color:{C_TEXT_DARK}; font-size:28px; font-weight:bold;")
        self.lbl_sottotitolo = QLabel("")
        self.lbl_sottotitolo.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:14px;")
        l_lay.addWidget(self.lbl_breadcrumb)
        l_lay.addWidget(self.lbl_titolo)
        l_lay.addWidget(self.lbl_sottotitolo)
        lay.addWidget(left)
        lay.addStretch()
        self.lbl_orologio = QLabel("")
        self.lbl_orologio.setStyleSheet(f"color:{C_TEXT_MID}; font-size:13px;")
        lay.addWidget(self.lbl_orologio, alignment=Qt.AlignRight | Qt.AlignVCenter)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._aggiorna_orologio)
        self._timer.start(30000)
        self._aggiorna_orologio()

    def _aggiorna_orologio(self):
        self.lbl_orologio.setText(datetime.now().strftime("%d %b %Y  ·  %H:%M"))

    def aggiorna(self, breadcrumb, titolo, sottotitolo):
        self.lbl_breadcrumb.setText(breadcrumb)
        self.lbl_titolo.setText(titolo)
        self.lbl_sottotitolo.setText(sottotitolo)


# ─────────────────────────────────────────────────────────────
# PAGINE
# ─────────────────────────────────────────────────────────────
class PaginaHome(QWidget):
    def __init__(self, nav_callback, paths: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C_BG};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(34, 28, 34, 28)
        lay.setSpacing(0)
        lbl_welcome = QLabel("ACCESSO RAPIDO")
        lbl_welcome.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:11px; font-weight:bold;")
        lay.addWidget(lbl_welcome)
        linea_red = QFrame()
        linea_red.setFixedSize(60, 3)
        linea_red.setStyleSheet(f"background:{C_RED}; border-radius:2px;")
        lay.addWidget(linea_red)
        lay.addSpacing(20)
        cards_frame = QFrame()
        cards_frame.setStyleSheet("background:transparent; border:none;")
        c_lay = QHBoxLayout(cards_frame)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(18)
        c_lay.addWidget(self._big_card("◈", "Giornalieri",
            "Seszione in cui puoi trovare tutti gli script utili per le operazioni quitidiane.\nPuoi trovare sia script inerenti a lato BUSINESS sia a lato CONSUMER",
            "Operatività quotidiana", "giornalieri", nav_callback))
        c_lay.addWidget(self._big_card("◉", "Campagne",
            "Divisione campagne per agente, avanzamento, report e statistiche complete.",
            "Gestione campagne", "campagne", nav_callback))
        lay.addWidget(cards_frame)
        lay.addSpacing(18)
        lay.addWidget(crea_section_label("Raw files · Input operativo"))
        lay.addSpacing(6)
        self.raw_files_widget = RawFilesWidget(paths["RAW_FILES"])
        lay.addWidget(self.raw_files_widget)
        lay.addStretch()
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll)

    def _big_card(self, icona, titolo, desc, tag, pagina, nav_callback):
        card = QFrame()
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setMinimumHeight(250)
        card.setStyleSheet(f"QFrame {{ background:{C_PANEL}; border-radius:14px; border:1px solid {C_BORDER}; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(26, 24, 26, 24)
        lay.setSpacing(0)
        lbl_tag = QLabel(f"  {tag}  ")
        lbl_tag.setStyleSheet(f"background:{C_FASTWEB}; color:#111827; border-radius:6px; font-size:11px; font-weight:bold; padding:2px 8px; border:none;")
        lbl_tag.setFixedHeight(24)
        lbl_tag.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lay.addWidget(lbl_tag)
        lay.addSpacing(14)
        lbl_icona = QLabel(icona)
        lbl_icona.setStyleSheet(f"font-size:32px; color:{C_RED}; background:transparent; border:none;")
        lay.addWidget(lbl_icona)
        lay.addSpacing(4)
        lbl_titolo = QLabel(titolo)
        lbl_titolo.setStyleSheet(f"font-size:20px; font-weight:bold; color:{C_TEXT_DARK}; background:transparent; border:none;")
        lay.addWidget(lbl_titolo)
        lay.addSpacing(6)
        lbl_desc = QLabel(desc)
        lbl_desc.setStyleSheet(f"font-size:14px; color:{C_TEXT_MID}; background:transparent; border:none;")
        lbl_desc.setWordWrap(True)
        lay.addWidget(lbl_desc)
        lay.addSpacing(20)
        btn = QPushButton("Apri sezione  →")
        btn.setStyleSheet(f"""
            QPushButton {{ background:{C_RED}; color:white; border:none; border-radius:12px; font-size:14px; font-weight:bold; padding:12px 20px; }}
            QPushButton:hover {{ background:{C_RED_HOVER}; }}
        """)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn.clicked.connect(lambda checked=False, p=pagina: nav_callback(p))
        lay.addWidget(btn)
        return card


class PaginaGiornalieri(QWidget):
    def __init__(self, terminale, paths: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C_BG};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        grid = QGridLayout(inner)
        grid.setContentsMargins(30, 14, 30, 24)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        for col in range(12): grid.setColumnStretch(col, 1)
        row = 0
        grid.addWidget(crea_section_label("Business"), row, 0, 1, 12); row += 1
        cards_business = [
            {"icona": "🗂️", "titolo": "1. Estrai file gara",
             "desc":  "Estrae da API, formatta e carica in un colpo solo gara, opportunità e appuntamenti.",
             "script": paths["ESTRAI_FILE_GARA"]},
            {"icona": "📈", "titolo": "2. FCST",
             "desc": "Generazione forecast giornaliero con reportistica automatica",
             "script": paths["FCST"]},
            {"icona": "📅", "titolo": "3. Appuntamenti",
             "desc": "Creazione report appuntamenti della settimana corrente per venditore",
             "script": paths["APPUNTAMENTI_SETTIMANA"]},
            {"icona": "📈", "titolo": "4. Performance Management CRM",
             "desc": "Genera le anteprime giornaliere delle azioni CRM da completare per ciascun commerciale.",
             "script": paths["PERFORMANCE_MANAGEMENT_CRM"]},
        ]
        business_start_row = row
        for i, cfg in enumerate(cards_business):
            card_row = business_start_row + i // 3
            card_column = i % 3
            grid.setRowMinimumHeight(card_row, CARD_HEIGHT_STATUS + 16)
            card = ScriptCard(cfg["icona"], cfg["titolo"], cfg["desc"], cfg["script"], terminale,
                              cartella=cfg.get("cartella"), nomi_file=cfg.get("nomi_file"))
            wrapper = QWidget(); wrapper.setStyleSheet("background:transparent;")
            w_lay = QVBoxLayout(wrapper); w_lay.setContentsMargins(0 if card_column == 0 else 8, 0, 0 if card_column == 2 else 8, 0); w_lay.setSpacing(0)
            w_lay.addWidget(card, alignment=Qt.AlignTop)
            grid.addWidget(wrapper, card_row, card_column * 4, 1, 4)
        row += (len(cards_business) + 2) // 3
        grid.addWidget(crea_section_label("Consumer / Negozi"), row, 0, 1, 12); row += 1
        cards_consumer = [
            {"icona": "🗂️", "titolo": "1. Formatta pedonalità",
             "desc": "Formatta e prepara il file pedonalità per le elaborazioni giornaliere.",
             "script": paths["FORMATTA_PEDONALITA"],
             "cartella": paths["RAW_FILES"], "nome_file": "Giorgio Mandelli*.xlsx"},
            {"icona": "📊", "titolo": "2. Cruscotto Tracciamento",
             "desc": "Report aggregato per Giorgio che riunisce Business, trattative Energia e vendite Gadget con eventuale cross selling, per monitorare l'esercizio dei negozi.",
             "script": paths["CRUSCOTTO_TRACCIAMENTO"]},
            {"icona": "📊", "titolo": "3. Cruscotto Giornaliero", 
             "desc": "Report aggregato per Giorgio e i referenti Fastweb+Vodafone che riunisce le 5 piste consumer: Mobile, Wireline, Upselling, Energy,",
             "script": paths["CRUSCOTTO_GIORNALIERO"]},
        ]
        grid.setRowMinimumHeight(row, CARD_HEIGHT + 16)
        for i, cfg in enumerate(cards_consumer):
            card = ScriptCard(cfg["icona"], cfg["titolo"], cfg["desc"], cfg["script"], terminale,
                              cartella=cfg.get("cartella"), nome_file=cfg.get("nome_file"),
                              nomi_file=cfg.get("nomi_file"))
            wrapper = QWidget(); wrapper.setStyleSheet("background:transparent;")
            w_lay = QVBoxLayout(wrapper); w_lay.setContentsMargins(0 if i == 0 else 8, 0, 0 if i == len(cards_consumer)-1 else 8, 0); w_lay.setSpacing(0)
            w_lay.addWidget(card, alignment=Qt.AlignTop)
            grid.addWidget(wrapper, row, i * 4, 1, 4)
        row += 1
        grid.setRowStretch(row, 1)
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll)


class PaginaCampagne(QWidget):
    def __init__(self, terminale, paths: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C_BG};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        grid = QGridLayout(inner)
        grid.setContentsMargins(30, 14, 30, 24)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        for col in range(12): grid.setColumnStretch(col, 1)
        row = 0
        grid.addWidget(crea_section_label("Campagne"), row, 0, 1, 12); row += 1
        cards = [
            {"icona": "👥", "titolo": "1. Divisione per agente",
             "desc": "Da eseguire dopo:\n - Aver asegnato venditore in ogni file\n - aver caricato il file dentro la cartella del periodo di riferimento dentro la cartella campagne",
             "script": paths["DIVIDI_FILE_CAMPAGNE"]},  
            {"icona": "📚", "titolo": "2. Riaggrega file Campagne",
             "desc": "Riaggrega i file delle campagne come in origine.\nPermette 2 funzionalità:\n 1 - Legge i dati dalle cartelle di ogni venditore (standard)\n 2 - Legge i file dalla cartella 'FILE RICEVUTI' (bisogna selezionarlo dal codice)",
             "script": paths["AGGREGA_FILE_VENDITORI"]},
            {"icona": "💼", "titolo": "3. Presa in carico cliente",
             "desc": "Legge tutti i file CAMPAGNA dei venditori e in quelli in cui la colonna 'Gestito (Si/No)' è si, lo lascia invariato, mentre se è no, lo assegna a CRM e pubblica il file per raul sul team CRM.\nNb. Da eseguire dopo aver lanciato lo script 2. Riaggrega file Campagne",
             "script": paths["PRESA_IN_CARICO"]},
            {"icona": "📋", "titolo": "4(⚒️). Report Campagne",
             "desc": "Genera report dettagliati: statistiche, KPI ed esiti campagne.",
             "script": paths["REPORT_CAMPAGNE"]},
        ]
        grid.setRowMinimumHeight(row, CARD_HEIGHT + 16)
        for i, cfg in enumerate(cards):
            card = ScriptCard(cfg["icona"], cfg["titolo"], cfg["desc"], cfg["script"], terminale,
                              cartella=cfg.get("cartella"), nomi_file=cfg.get("nomi_file"))
            wrapper = QWidget(); wrapper.setStyleSheet("background:transparent;")
            w_lay = QVBoxLayout(wrapper); w_lay.setContentsMargins(0 if i == 0 else 8, 0, 0 if i == len(cards)-1 else 8, 0); w_lay.setSpacing(0)
            w_lay.addWidget(card, alignment=Qt.AlignTop)
            grid.addWidget(wrapper, row, i * 3, 1, 3)
        row += 1
        grid.setRowStretch(row, 1)
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll)

class PaginaAltriScript(QWidget):
    def __init__(self, terminale, paths: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C_BG};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        grid = QGridLayout(inner)
        grid.setContentsMargins(30, 14, 30, 24)
        grid.setHorizontalSpacing(0); grid.setVerticalSpacing(0)
        for col in range(12): grid.setColumnStretch(col, 1)
        row = 0
        grid.addWidget(crea_section_label("Business"), row, 0, 1, 12); row += 1
        cards_business = [
            {"icona" : "🗂️", "titolo" : "1. Formatta gara",
             "desc" : "Estrae dal CRM gara, appuntamenti e opportunità, li elabora e li carica in automatico.",
             "script" : paths["FORMATTA_GARA"]},

            {"icona" : "📈", "titolo" : "2. Formatta file appuntamenti", 
             "desc" : "Elabora il file appuntamenti estratto dal CRM e lo prepara per l'utilizzo.",
             "script" : paths["FORMATTA_APPUNTAMENTI"]},

            {"icona" : "📅", "titolo" : "3. Formatta file opportunità",
             "desc" : "Elabora il file opportunità estratto dal CRM e lo prepara per l'utilizzo.",
             "script" : paths["FORMATTA_OPPORTUNITA"]},

            {"icona" : "🔒", "titolo" : "4. Chiusura gara",
             "desc" : "Estrae dal CRM gli ordini attivati nella gara precedente. Un click, poi trovi il file su Teams.",
             "script" : paths["CHIUSURA_GARA"]},
        ]
        grid.setRowMinimumHeight(row, CARD_HEIGHT + 16)
        for i, cfg in enumerate(cards_business):
            card = ScriptCard(cfg["icona"], cfg["titolo"], cfg["desc"], cfg["script"], terminale,
                              cartella=cfg.get("cartella"), nomi_file=cfg.get("nomi_file"))
            wrapper = QWidget(); wrapper.setStyleSheet("background:transparent;")
            w_lay = QVBoxLayout(wrapper); w_lay.setContentsMargins(0 if i == 0 else 8, 0, 0 if i == len(cards_business)-1 else 8, 0); w_lay.setSpacing(0)
            w_lay.addWidget(card, alignment=Qt.AlignTop)
            grid.addWidget(wrapper, row, i * 3, 1, 3)
        row += 1
          
        #SEZIONE FILE NEGOZI
        grid.addWidget(crea_section_label("Strumenti file negozi"), row, 0, 1, 12); row += 1
        cards_consumer = [
            ("📊", "1. Report pedonalità",    "Crea il report di analisi dei flussi di pedonalità", paths["REPORT_PEDONALITA"], None, None),
            ("🏬", "2. Formatta magazzino",    "Formatta file magazzino e classifica articoli", paths["FORMATTA_MAGAZZINO"],   paths["RAW_FILES"], "VALORE_DEL_MAGAZZINO*.csv"),
            ("📊", "3(⚒️). Formatta performance",  "Formatta file performances",                    "",                           paths["RAW_FILES"], ""),
        ]
        grid.setRowMinimumHeight(row, CARD_HEIGHT + 16)
        for i, (icona, titolo, desc, script, cartella, nome_file) in enumerate(cards_consumer):
            card = ScriptCard(icona, titolo, desc, script, terminale, cartella=cartella, nome_file=nome_file)
            wrapper = QWidget(); wrapper.setStyleSheet("background:transparent;")
            w_lay = QVBoxLayout(wrapper); w_lay.setContentsMargins(0 if i == 0 else 8, 0, 0 if i == len(cards_consumer)-1 else 8, 0); w_lay.setSpacing(0)
            w_lay.addWidget(card, alignment=Qt.AlignTop)
            grid.addWidget(wrapper, row, i * 4, 1, 4)
        row += 1
        grid.setRowStretch(row, 1)
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll)


# ─────────────────────────────────────────────────────────────
# FINESTRA PRINCIPALE
# ─────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, sharepoint_root: Path):
        super().__init__()
        self.sharepoint_root = sharepoint_root
        self.paths = _build_paths(sharepoint_root)
        os.environ["BASE_DIR"] = str(sharepoint_root)
        os.environ["MYWAY_SHAREPOINT_ROOT"] = str(sharepoint_root)

        self.setWindowTitle("MyWay Tools")
        self.resize(1280, 800)
        self.setMinimumSize(1000, 650)
        self.setStyleSheet(f"background:{C_BG};")
        self.setWindowIcon(carica_icona())
        self.pagina_corrente = "main"

        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QHBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        self.sidebar_stack = QStackedWidget()
        self.sidebar_stack.setFixedWidth(280)
        self.sidebar_stack.setStyleSheet(f"background:{C_SIDEBAR}; border:none;")
        main_lay.addWidget(self.sidebar_stack)

        right = QWidget()
        right.setStyleSheet(f"background:{C_BG};")
        r_lay = QVBoxLayout(right)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(0)

        self.header = GlobalHeader()
        r_lay.addWidget(self.header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C_BORDER};")
        r_lay.addWidget(sep)

        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"background:{C_BG};")
        self.terminale = TerminaleWidget()
        self.workspace_splitter = QSplitter(Qt.Vertical)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setHandleWidth(5)
        self.workspace_splitter.setStyleSheet("""
            QSplitter::handle { background:#DCE1E8; }
            QSplitter::handle:hover { background:#E30613; }
        """)
        self.workspace_splitter.addWidget(self.content_stack)
        self.workspace_splitter.addWidget(self.terminale)
        self.workspace_splitter.setStretchFactor(0, 1)
        self.workspace_splitter.setStretchFactor(1, 0)
        self.workspace_splitter.setSizes([700, 190])
        r_lay.addWidget(self.workspace_splitter, stretch=1)
        main_lay.addWidget(right, stretch=1)

        self._build_all()
        self.mostra_pagina("main")
        self.showMaximized()

    def _build_all(self):
        self.sidebars = {}
        self.pages    = {}
        for nome in ("main", "giornalieri", "campagne", "altri script"):
            sb = Sidebar(nome, self.mostra_pagina, self.sharepoint_root)
            self.sidebar_stack.addWidget(sb)
            self.sidebars[nome] = sb

        self.pages["main"]         = PaginaHome(self.mostra_pagina, self.paths)
        self.pages["giornalieri"]  = PaginaGiornalieri(self.terminale, self.paths)
        self.pages["campagne"]     = PaginaCampagne(self.terminale, self.paths)
        self.pages["altri script"] = PaginaAltriScript(self.terminale, self.paths)

        for page in self.pages.values():
            self.content_stack.addWidget(page)

    def mostra_pagina(self, nome):
        # Intercetta il comando speciale "cambia sharepoint"
        if nome == "_cambia_sharepoint":
            self._cambia_sharepoint()
            return

        self.sidebar_stack.setCurrentWidget(self.sidebars[nome])
        self.content_stack.setCurrentWidget(self.pages[nome])
        self.pagina_corrente = nome

        dati = {
            "main":         ("", "MyWay Tools",   "Seleziona una sezione per accedere agli script."),
            "giornalieri":  ("", "Giornalieri",   "Script operativi per le attività quotidiane."),
            "campagne":     ("", "Campagne",       "Gestione e monitoraggio campagne."),
            "altri script": ("", "Altri Script",  "Script aggiuntivi per operazioni specifiche."),
        }
        self.header.aggiorna(*dati.get(nome, ("Home", "Dashboard", "")))

    def _cambia_sharepoint(self):
        """Apre la dialog di configurazione per cambiare la root SharePoint."""
        dlg = ConfigDialog(
            "Stai modificando la cartella SharePoint. L'app si riavvierà.",
            parent=self
        )
        if dlg.exec() == QDialog.Accepted and dlg.sharepoint_root:
            QMessageBox.information(
                self, "Configurazione salvata",
                f"La nuova cartella SharePoint è:\n{dlg.sharepoint_root}\n\n"
                "Riavvia l'applicazione per applicare le modifiche."
            )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            QApplication.quit()


# ─────────────────────────────────────────────────────────────
# INTERFACCIA OPERATIVA 2.0
# ─────────────────────────────────────────────────────────────
class WorkspaceNavButton(QPushButton):
    def __init__(self, icon, text, page, callback, parent=None):
        super().__init__(text, parent)
        self.page = page
        role(self, "navigation")
        self.setProperty("page", page)
        self.setIcon(line_icon(icon, "#396A9B" if page == "workflows" else Theme.MUTED))
        self.setIconSize(QSize(20, 20))
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)
        self.clicked.connect(lambda checked=False: callback(page))


class WorkspaceSidebar(QFrame):
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.setObjectName("workspaceSidebar")
        self.setFixedWidth(Theme.SIDEBAR_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 18)
        layout.setSpacing(6)

        brand = QFrame()
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(8, 0, 0, 24)
        brand_layout.setSpacing(12)
        icon = QLabel()
        icon.setPixmap(carica_icona().pixmap(QSize(36, 36)))
        brand_layout.addWidget(icon)
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = role(QLabel("MyWay Tools"), "section")
        subtitle = role(QLabel("Spazio operativo"), "secondary")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        brand_layout.addLayout(title_box)
        brand_layout.addStretch()
        layout.addWidget(brand)

        label = role(QLabel("  WORKSPACE"), "eyebrow")
        layout.addWidget(label)
        layout.addSpacing(6)

        self.buttons = {}
        self.group = QButtonGroup(self)
        for icon, text, page in (
            ("today", "Oggi", "today"),
            ("all", "Tutte le attività", "all"),
            ("business", "Business", "business"),
            ("consumer", "Consumer", "consumer"),
            ("campaigns", "Campagne", "campaigns"),
            ("files", "File", "files"),
            ("today", "Storico", "history"),
            ("play", "Workflow", "workflows"),
            ("chart", "Riepilogo", "summary"),
        ):
            button = WorkspaceNavButton(icon, text, page, callback)
            self.buttons[page] = button
            self.group.addButton(button)
            layout.addWidget(button)

        layout.addStretch()
        line = role(QFrame(), "separator")
        line.setFixedHeight(1)
        layout.addWidget(line)
        layout.addSpacing(8)
        info = role(QLabel("FASTWEB + VODAFONE\nAutomazioni operative"), "secondary")
        info.setContentsMargins(8, 4, 0, 10)
        layout.addWidget(info)
        exit_button = role(QPushButton("Esci"), "navigation")
        exit_button.setIcon(line_icon("exit"))
        exit_button.setCursor(Qt.PointingHandCursor)
        exit_button.setMinimumHeight(38)
        exit_button.clicked.connect(lambda: self.window().close())
        layout.addWidget(exit_button)

    def select(self, page):
        if page in self.buttons:
            self.buttons[page].setChecked(True)


class WorkspaceHeader(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workspaceHeader")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(8)
        top = QHBoxLayout()
        self.eyebrow = role(QLabel("WORKSPACE"), "eyebrow")
        top.addWidget(self.eyebrow)
        top.addStretch()
        self.clock = role(QLabel(), "secondary")
        top.addWidget(self.clock)
        layout.addLayout(top)
        self.title = role(QLabel("Oggi"), "title")
        self.title.setWordWrap(True)
        self.subtitle = role(QLabel(), "secondary")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(30000)
        self.update_clock()

    def update_clock(self):
        self.clock.setText(datetime.now().strftime("%d.%m.%Y"))

    def set_page(self, eyebrow, title, subtitle):
        self.eyebrow.setText(eyebrow.upper())
        self.title.setText(title)
        self.subtitle.setText(subtitle)


class WorkflowRow(QFrame):
    def __init__(self, number, title, description, script, terminal,
                 category="", folder=None, filename=None, parent=None):
        super().__init__(parent)
        self.script = Path(script) if script else None
        self.terminal = terminal
        self.folder = Path(folder) if folder else None
        self.filename = filename
        self.running = False
        self.available = bool(self.script and self.script.is_file())
        self.setFixedHeight(98)
        self.setStyleSheet(f"""
            WorkflowRow {{ background:{C_PANEL}; border:1px solid {C_BORDER}; border-radius:11px; }}
            WorkflowRow:hover {{ border:1px solid #C7CDD6; }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)
        index = QLabel(str(number).zfill(2))
        index.setAlignment(Qt.AlignCenter)
        index.setFixedSize(44, 44)
        index.setStyleSheet(f"background:{C_FASTWEB}; color:#111827; border-radius:9px; font-size:15px; font-weight:bold;")
        layout.addWidget(index)

        copy = QVBoxLayout()
        copy.setSpacing(3)
        top = QHBoxLayout()
        name = QLabel(title)
        name.setStyleSheet(f"color:{C_TEXT_DARK}; font-size:16px; font-weight:bold;")
        top.addWidget(name)
        if category:
            tag = QLabel(category.upper())
            tag.setStyleSheet(f"background:{C_FASTWEB_LIGHT}; color:#665700; border-radius:5px; padding:2px 7px; font-size:9px; font-weight:bold;")
            tag.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            top.addWidget(tag)
        top.addStretch()
        copy.addLayout(top)
        detail = QLabel(description)
        detail.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:13px;")
        detail.setWordWrap(True)
        copy.addWidget(detail)
        self.status = QLabel()
        self.status.setStyleSheet(f"color:{C_TEXT_MID}; font-size:11px;")
        copy.addWidget(self.status)
        layout.addLayout(copy, stretch=1)

        self.run_button = QPushButton("Avvia")
        self.run_button.setCursor(Qt.PointingHandCursor)
        self.run_button.setFixedSize(112, 38)
        self.run_button.setStyleSheet(f"""
            QPushButton {{ background:{C_RED}; color:white; border:none; border-radius:8px;
                           font-size:13px; font-weight:bold; }}
            QPushButton:hover {{ background:{C_RED_HOVER}; }}
            QPushButton:disabled {{ background:#D4D8DE; color:#7B8494; }}
        """)
        self.run_button.clicked.connect(self.run)
        layout.addWidget(self.run_button)

        self.signals = ScriptCardSignals()
        self.signals.script_finished.connect(self.finished)
        global_signals.script_avviato.connect(self.lock)
        global_signals.script_terminato.connect(self.unlock)
        self.refresh_status()

    def refresh_status(self):
        if not self.available:
            self.status.setText("Funzione in sviluppo")
            self.run_button.setText("Non disponibile")
            self.run_button.setFixedWidth(126)
            self.run_button.setEnabled(False)
            return
        if self.folder and self.filename:
            found, match = check_file_per_nome(self.folder, self.filename)
            self.status.setText(f"Pronto · {match}" if found else f"In attesa di {self.filename}")
            self.status.setStyleSheet(
                f"color:{C_LOG_OK if found else C_LOG_WARN}; font-size:11px; font-weight:bold;")
            self.run_button.setEnabled(found)
        else:
            self.status.setText("Pronto per l'esecuzione")
            self.run_button.setEnabled(True)

    def run(self):
        if not self.available or self.running:
            return
        self.running = True
        self.run_button.setText("In esecuzione")
        lancia_script(self.script, self.terminal, self.signals.script_finished.emit)

    def finished(self, success):
        self.running = False
        self.status.setText("Completato correttamente" if success else "Terminato con errore")
        self.status.setStyleSheet(
            f"color:{C_LOG_OK if success else C_LOG_ERR}; font-size:11px; font-weight:bold;")

    def lock(self):
        if not self.running:
            self.run_button.setEnabled(False)

    def unlock(self):
        if not self.running:
            self.run_button.setText("Avvia" if self.available else "Non disponibile")
            self.refresh_status()


class SharePointCheck(QObject):
    """The existing remote preflight, shared by the inline panel and legacy dialog."""

    finished = Signal(bool, str)
    _result_ready = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self._result_ready.connect(self._completed, Qt.QueuedConnection)

    @Slot(bool, str)
    def _completed(self, ready, message):
        self.running = False
        self.finished.emit(ready, message)

    def start(self):
        if self.running:
            return
        self.running = True

        def check_cb():
            marker = "__MYWAY_CB_CHECK__"
            bootstrap = r'''import json, sys
from pathlib import Path
scripts = Path(sys.argv[1])
module = scripts / "BUSINESS" / "14_ELABORA_CB"
sys.path[:0] = [str(module), str(scripts)]
from cb_sharepoint import PATH_RAW_CB_REMOTO, _drive, _file_dati
client, drive_id = _drive()
files = [item for item in client.elenca_file_cartella(drive_id, PATH_RAW_CB_REMOTO) if _file_dati(item)]
matches = [item for item in files if "cb" in str(item.get("name", "")).casefold()]
matches.sort(key=lambda item: str(item.get("lastModifiedDateTime", "")), reverse=True)
print("__MYWAY_CB_CHECK__" + json.dumps({"found": bool(matches), "name": str(matches[0].get("name", "")) if matches else ""}))'''
            try:
                completed = subprocess.run(
                    [_trova_python(), "-u", "-c", bootstrap, str(SCRIPTS_DIR)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=40, creationflags=subprocess.CREATE_NO_WINDOW,
                )
                payload_line = next(
                    (line for line in reversed(completed.stdout.splitlines()) if line.startswith(marker)),
                    None,
                )
                if completed.returncode != 0 or not payload_line:
                    raise RuntimeError("Controllo SharePoint non completato")
                payload = json.loads(payload_line[len(marker):])
                if payload.get("found"):
                    result = (True, f"File CB trovato su SharePoint: {payload.get('name')}")
                else:
                    result = (False, "Nessun file contenente “CB” trovato in 00_DA_ELABORARE.")
            except subprocess.TimeoutExpired:
                result = (False, "Verifica SharePoint interrotta dopo 40 secondi. Riprova.")
            except Exception:
                result = (False, "Impossibile verificare SharePoint. Controlla la connessione e riprova.")
            self._result_ready.emit(*result)

        threading.Thread(target=check_cb, daemon=True).start()


class ScriptLaunchDialog(QDialog):
    def __init__(self, tile, parent=None):
        super().__init__(parent)
        self.tile = tile
        self.setWindowTitle(tile.title)
        self.setModal(True)
        self.setFixedWidth(520)
        self.setStyleSheet(f"background:{C_PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(12)

        top = QHBoxLayout()
        badge = QLabel(str(tile.number).zfill(2))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(42, 34)
        badge.setStyleSheet(f"background:{C_FASTWEB}; color:#111827; border-radius:7px; font-weight:bold;")
        top.addWidget(badge)
        category = QLabel(tile.category.upper())
        category.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:11px; font-weight:bold;")
        top.addWidget(category)
        top.addStretch()
        layout.addLayout(top)

        title = QLabel(tile.title)
        title.setStyleSheet(f"color:{C_TEXT_DARK}; font-size:23px; font-weight:bold;")
        layout.addWidget(title)
        description = QLabel(tile.description)
        description.setWordWrap(True)
        description.setStyleSheet(f"color:{C_TEXT_MID}; font-size:14px;")
        layout.addWidget(description)

        if tile.instructions:
            instructions_title = QLabel("COME RECUPERARE IL FILE")
            instructions_title.setStyleSheet(f"color:{C_RED}; font-size:10px; font-weight:bold;")
            layout.addWidget(instructions_title)
            instructions = QLabel(tile.instructions)
            instructions.setWordWrap(True)
            instructions.setStyleSheet(f"color:{C_TEXT_MID}; font-size:13px;")
            layout.addWidget(instructions)

        status_title = QLabel("CONTROLLO PRIMA DELL'AVVIO")
        status_title.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:10px; font-weight:bold;")
        layout.addWidget(status_title)
        ready, message = tile.readiness()
        if tile.remote_check:
            ready = False
            message = "Verifica della cartella SharePoint in corso..."
        self.status = QLabel(message)
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color:{C_LOG_INFO if tile.remote_check else (C_LOG_OK if ready else C_LOG_WARN)}; "
            "font-size:13px; font-weight:bold;")
        layout.addWidget(self.status)

        self.add_file_button = None
        if tile.available and tile.folder and tile.filename and not ready:
            self.add_file_button = QPushButton("+ Aggiungi file alla cartella RAW")
            self.add_file_button.setCursor(Qt.PointingHandCursor)
            self.add_file_button.setFixedHeight(38)
            self.add_file_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.add_file_button.setStyleSheet(f"""
                QPushButton {{ background:{C_FASTWEB}; color:#111827; border:none; border-radius:7px;
                               padding:0 15px; font-size:12px; font-weight:bold; }}
                QPushButton:hover {{ background:{C_FASTWEB_HOVER}; }}
            """)
            self.add_file_button.clicked.connect(self._add_file)
            layout.addWidget(self.add_file_button, alignment=Qt.AlignLeft)

        self.remote_check_button = None
        self.remote_check_signals = None
        self._remote_check_running = False
        if tile.remote_check:
            self.remote_check_button = QPushButton("Riprova controllo")
            self.remote_check_button.setCursor(Qt.PointingHandCursor)
            self.remote_check_button.setFixedHeight(36)
            self.remote_check_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.remote_check_button.setStyleSheet(f"""
                QPushButton {{ background:{C_BG}; color:{C_TEXT_MID}; border:1px solid {C_BORDER};
                               border-radius:7px; padding:0 14px; font-size:12px; font-weight:bold; }}
                QPushButton:hover {{ border-color:{C_RED}; color:{C_RED}; }}
                QPushButton:disabled {{ color:#9CA3AF; }}
            """)
            self.remote_check_button.clicked.connect(self._start_remote_check)
            self.remote_check_button.hide()
            layout.addWidget(self.remote_check_button, alignment=Qt.AlignLeft)

        hint = QLabel("Dopo l'avvio puoi seguire tutte le fasi nel terminale in basso.")
        hint.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:12px;")
        layout.addWidget(hint)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Annulla")
        cancel.setFixedHeight(38)
        cancel.setStyleSheet(f"background:{C_BG}; color:{C_TEXT_MID}; border:1px solid {C_BORDER}; border-radius:8px; padding:0 16px;")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        self.run_button = QPushButton("Avvia elaborazione")
        self.run_button.setFixedHeight(38)
        self.run_button.setStyleSheet(f"""
            QPushButton {{ background:{C_RED}; color:white; border:none; border-radius:8px;
                           padding:0 18px; font-size:13px; font-weight:bold; }}
            QPushButton:hover {{ background:{C_RED_HOVER}; }}
            QPushButton:disabled {{ background:#D4D8DE; color:#7B8494; }}
        """)
        self.run_button.setEnabled(ready)
        self.run_button.clicked.connect(self._run)
        actions.addWidget(self.run_button)
        layout.addLayout(actions)

        if tile.remote_check:
            self.remote_check_signals = RemoteCheckSignals(self)
            self.remote_check_signals.finished.connect(self._remote_check_finished)
            self._remote_checker = SharePointCheck(self)
            self._remote_checker.finished.connect(self.remote_check_signals.finished.emit)
            QTimer.singleShot(0, self._start_remote_check)

    def _start_remote_check(self):
        if self._remote_check_running or self.tile.remote_check != "sharepoint_cb":
            return
        self._remote_check_running = True
        self.run_button.setEnabled(False)
        self.status.setText("Verifica della cartella SharePoint in corso...")
        self.status.setStyleSheet(f"color:{C_LOG_INFO}; font-size:13px; font-weight:bold;")
        if self.remote_check_button:
            self.remote_check_button.hide()

        self._remote_checker.start()

    def _remote_check_finished(self, ready, message):
        self._remote_check_running = False
        self.status.setText(message)
        self.status.setStyleSheet(
            f"color:{C_LOG_OK if ready else C_LOG_WARN}; font-size:13px; font-weight:bold;")
        self.run_button.setEnabled(ready)
        if self.remote_check_button:
            self.remote_check_button.setVisible(not ready)

    def _add_file(self):
        selected, _ = QFileDialog.getOpenFileName(
            self, "Scegli il file da aggiungere", str(Path.home()), "Tutti i file (*.*)")
        if not selected:
            return
        source = Path(selected)
        try:
            self.tile.folder.mkdir(parents=True, exist_ok=True)
            destination = self.tile.folder / source.name
            if destination.exists():
                answer = QMessageBox.question(
                    self, "File già presente", f"Sovrascrivere «{source.name}»?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer != QMessageBox.Yes:
                    return
            shutil.copy2(source, destination)
        except OSError as error:
            QMessageBox.critical(self, "Errore copia", f"Impossibile aggiungere il file:\n{error}")
            return
        self.tile.refresh_status()
        ready, message = self.tile.readiness()
        self.status.setText(message)
        self.status.setStyleSheet(
            f"color:{C_LOG_OK if ready else C_LOG_WARN}; font-size:13px; font-weight:bold;")
        self.run_button.setEnabled(ready)
        if ready and self.add_file_button:
            self.add_file_button.hide()

    def _run(self):
        self.accept()
        lancia_script(
            self.tile.script, self.tile.terminal,
            lambda success: None)


def emoji_script(title):
    """Restituisce un simbolo immediato e coerente con lo scopo dello script."""
    text = title.casefold()
    rules = (
        ("chiusura gara", "🔒"), ("giacenze", "📱"),
        ("magazzino", "📦"), ("pedonalità", "👣"),
        ("forecast", "📈"), ("appuntamenti", "📅"),
        ("opportunità", "🎯"), ("divisione", "👥"),
        ("riaggrega", "🗃️"), ("presa in carico", "💼"),
        ("campagne", "📣"), ("cruscotto", "📊"),
        ("elabora cb", "🧾"), ("gara", "🗂️"),
    )
    return next((icon for keyword, icon in rules if keyword in text), "⚙️")


class ScriptTile(QFrame):
    def __init__(self, number, title, description, script, terminal,
                 category="", folder=None, filename=None, instructions="", remote_check=None,
                 expected_count=1,
                 parent=None):
        super().__init__(parent)
        self.number = number
        self.title = title
        self.description = description
        self.script = Path(script) if script else None
        self.terminal = terminal
        self.category = category
        self.folder = Path(folder) if folder else None
        self.filename = filename
        self.expected_count = expected_count
        self.instructions = instructions.strip() if instructions else ""
        self.remote_check = remote_check
        self.available = bool(self.script and self.script.is_file())
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(224)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(f"""
            ScriptTile {{ background:{C_PANEL}; border:1px solid {C_BORDER}; border-radius:13px; }}
            ScriptTile:hover {{ border:1px solid {C_RED}; background:#FFFFFF; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(9)

        accent = QFrame()
        accent.setFixedHeight(4)
        accent.setStyleSheet(f"background:{C_RED}; border:none; border-radius:2px;")
        layout.addWidget(accent)

        top = QHBoxLayout()
        badge = QLabel(str(number).zfill(2))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(36, 28)
        badge.setStyleSheet(f"background:{C_FASTWEB}; color:#111827; border-radius:6px; font-size:12px; font-weight:bold;")
        top.addWidget(badge)
        top.addStretch()
        tag = QLabel(category.upper())
        tag.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        tag.setStyleSheet(f"background:#EEF1F5; color:{C_TEXT_MID}; border:none; border-radius:5px; padding:3px 7px; font-size:9px; font-weight:bold;")
        top.addWidget(tag)
        layout.addLayout(top)

        name = QLabel(f"{emoji_script(title)}  {title}")
        name.setWordWrap(True)
        name.setStyleSheet(f"background:transparent; border:none; color:{C_TEXT_DARK}; font-size:18px; font-weight:bold;")
        layout.addWidget(name)
        detail = QLabel(description)
        detail.setWordWrap(True)
        detail.setStyleSheet(f"background:transparent; border:none; color:{C_TEXT_LIGHT}; font-size:13px;")
        layout.addWidget(detail)

        layout.addStretch()

        bottom = QHBoxLayout()
        self.status = QLabel()
        self.status.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.status.setWordWrap(True)
        bottom.addWidget(self.status)
        bottom.addStretch()
        self.open_button = QPushButton("Apri  →")
        self.open_button.setCursor(Qt.PointingHandCursor)
        self.open_button.setFixedSize(90, 34)
        self.open_button.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{C_RED}; border:1px solid {C_RED};
                           border-radius:7px; font-size:12px; font-weight:bold; }}
            QPushButton:hover {{ background:{C_RED_LIGHT}; }}
            QPushButton:disabled {{ color:#9CA3AF; border-color:#D4D8DE; }}
        """)
        self.open_button.clicked.connect(self.open_dialog)
        bottom.addWidget(self.open_button)
        layout.addLayout(bottom)
        global_signals.script_avviato.connect(lambda: self.open_button.setEnabled(False))
        global_signals.script_terminato.connect(self.refresh_status)
        self.status_timer = None
        if self.folder and self.filename:
            self.status_timer = QTimer(self)
            self.status_timer.timeout.connect(self.refresh_status)
            self.status_timer.start(3000)
        self.refresh_status()

    def readiness(self):
        if not self.available:
            return False, "Funzione non ancora disponibile."
        if self.folder and self.filename:
            matches = [file for file in self.folder.glob(self.filename) if file.is_file()]
            count = len(matches)
            if self.expected_count > 1:
                if count == self.expected_count:
                    return True, f"Tutti i file richiesti sono presenti: {count}/{self.expected_count}."
                if count < self.expected_count:
                    return False, f"File presenti: {count}/{self.expected_count}. Ne mancano {self.expected_count - count}."
                return False, f"File presenti: {count}/{self.expected_count}. Rimuovi i {count - self.expected_count} file in eccesso."
            if matches:
                return True, f"File trovato: {matches[0].name}"
            return False, f"File richiesto non trovato: {self.filename}"
        return True, "Tutto pronto per l'esecuzione."

    def refresh_status(self):
        ready, message = self.readiness()
        if not self.available:
            short = "In sviluppo"
        elif self.remote_check:
            short = "Verifica all'apertura"
        elif self.filename:
            if self.expected_count > 1:
                count = len([file for file in self.folder.glob(self.filename) if file.is_file()])
                short = f"File presenti {count}/{self.expected_count}"
            else:
                short = "File pronto" if ready else "File mancante"
        else:
            short = "Pronto"
        self.status.setText(short)
        status_color = C_LOG_INFO if self.remote_check and self.available else (C_LOG_OK if ready else C_LOG_WARN)
        self.status.setStyleSheet(
            f"background:#F1F3F6; color:{status_color}; border:none; "
            "border-radius:5px; padding:3px 7px; font-size:11px; font-weight:bold;")
        self.open_button.setEnabled(self.available)
        self.open_button.setText("Apri  →" if self.available else "In sviluppo")

    def open_dialog(self):
        if self.available:
            # Il contenuto della cartella può cambiare per effetto della
            # sincronizzazione SharePoint: aggiorna il badge prima del popup.
            self.refresh_status()
            ScriptLaunchDialog(self, self.window()).exec()
            self.refresh_status()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.available:
            self.open_dialog()
        super().mousePressEvent(event)


class WorkflowPage(QWidget):
    def __init__(self, groups, terminal, columns=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C_BG};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        body = QWidget()
        body.setStyleSheet(f"background:{C_BG};")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(30, 18, 30, 28)
        layout.setSpacing(10)
        number = 1
        for group_name, items in groups:
            heading = QLabel(group_name.upper())
            heading.setStyleSheet(f"color:{C_TEXT_MID}; font-size:11px; font-weight:bold; padding:14px 2px 3px 2px;")
            layout.addWidget(heading)
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            column_count = columns or min(4, max(1, len(items)))
            for i, item in enumerate(items):
                grid.addWidget(ScriptTile(
                    number, item[0], item[1], item[2], terminal,
                    category=group_name, folder=item[3] if len(item) > 3 else None,
                    filename=item[4] if len(item) > 4 else None,
                    instructions=item[5] if len(item) > 5 else "",
                    remote_check=item[6] if len(item) > 6 else None,
                    expected_count=item[7] if len(item) > 7 else 1),
                    i // column_count, i % column_count)
                number += 1
            for column in range(column_count):
                grid.setColumnStretch(column, 1)
            layout.addLayout(grid)
        layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll)


class DashboardPage(QWidget):
    def __init__(self, navigate, paths, on_raw_folder_changed, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C_BG};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        body = QWidget()
        body.setStyleSheet(f"background:{C_BG};")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(30, 24, 30, 28)
        layout.setSpacing(16)

        intro = QFrame()
        intro.setStyleSheet(f"background:{C_SIDEBAR}; border:none; border-radius:14px;")
        intro_layout = QHBoxLayout(intro)
        intro_layout.setContentsMargins(26, 20, 22, 20)
        intro_copy = QVBoxLayout()
        intro_copy.setSpacing(4)
        title = QLabel("Da dove vuoi iniziare?")
        title.setStyleSheet("color:white; font-size:21px; font-weight:bold;")
        sub = QLabel("Scegli un flusso oppure prepara i file di input qui sotto.")
        sub.setStyleSheet("color:#AFB8C7; font-size:13px;")
        intro_copy.addWidget(title)
        intro_copy.addWidget(sub)
        intro_layout.addLayout(intro_copy)
        intro_layout.addStretch()
        for text, page, primary in (("Giornalieri", "operations", True), ("Utilità", "tools", False)):
            button = QPushButton(text)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(40)
            if primary:
                button.setStyleSheet(f"background:{C_FASTWEB}; color:#111827; border:none; border-radius:8px; padding:0 18px; font-weight:bold;")
            else:
                button.setStyleSheet("background:#263346; color:white; border:1px solid #3B4759; border-radius:8px; padding:0 18px; font-weight:bold;")
            button.clicked.connect(lambda checked=False, p=page: navigate(p))
            intro_layout.addWidget(button)
        layout.addWidget(intro)

        workflow_title = QLabel("FLUSSO DI LAVORO")
        workflow_title.setStyleSheet(
            f"color:{C_TEXT_MID}; font-size:11px; font-weight:bold; padding-top:6px;")
        layout.addWidget(workflow_title)

        steps = QFrame()
        steps.setFixedHeight(58)
        steps.setStyleSheet(f"background:{C_PANEL}; border:1px solid {C_BORDER}; border-radius:11px;")
        steps_layout = QHBoxLayout(steps)
        steps_layout.setContentsMargins(8, 7, 8, 7)
        steps_layout.setSpacing(6)
        for number, icon, title, detail in (
            ("1", "▣", "Prepara", "Scegli la cartella RAW"),
            ("2", "＋", "Carica", "Aggiungi i file richiesti"),
            ("3", "▶", "Esegui", "Apri un flusso e avvia"),
            ("4", "✓", "Controlla", "Verifica l'esito finale"),
        ):
            step_card = QFrame()
            step_card.setStyleSheet(
                f"background:{C_FASTWEB_LIGHT if number == '1' else '#F7F8FA'}; "
                "border:none; border-radius:8px;")
            step = QHBoxLayout(step_card)
            step.setContentsMargins(8, 4, 9, 4)
            step.setSpacing(7)
            badge = QLabel(number)
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(30, 30)
            badge.setStyleSheet(
                f"background:{C_FASTWEB if number == '1' else C_SIDEBAR}; color:{'#111827' if number == '1' else 'white'}; "
                "border-radius:15px; font-size:12px; font-weight:bold;")
            step.addWidget(badge)
            copy = QVBoxLayout()
            copy.setSpacing(0)
            heading = QLabel(f"{icon}  {title}")
            heading.setStyleSheet(f"color:{C_TEXT_DARK}; font-size:12px; font-weight:bold;")
            caption = QLabel(detail)
            caption.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:10px;")
            copy.addWidget(heading)
            copy.addWidget(caption)
            step.addLayout(copy)
            steps_layout.addWidget(step_card, stretch=1)
            if number != "4":
                arrow = QLabel("›")
                arrow.setAlignment(Qt.AlignCenter)
                arrow.setFixedWidth(10)
                arrow.setStyleSheet(f"color:{C_RED}; font-size:20px; font-weight:bold;")
                steps_layout.addWidget(arrow)
        layout.addWidget(steps)

        raw_title = QLabel("RAW FILES")
        raw_title.setStyleSheet(f"color:{C_TEXT_MID}; font-size:11px; font-weight:bold; padding-top:6px;")
        layout.addWidget(raw_title)
        self.raw_files_widget = RawFilesWidget(
            paths["RAW_FILES"], on_folder_changed=on_raw_folder_changed)
        layout.addWidget(self.raw_files_widget)
        layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll)


@dataclass
class ActivitySpec:
    number: int
    title: str
    description: str
    category: str
    script: Path | None
    terminal: TerminaleWidget
    folder: Path | None = None
    filename: str | None = None
    instructions: str = ""
    remote_check: str | None = None
    expected_count: int = 1
    activity_id: str = ""
    output_validator: object = None

    @property
    def available(self):
        if hasattr(self, "status_service"):
            return self.status_service.state(self).available
        return bool(self.script and self.script.is_file())

    def readiness(self):
        if hasattr(self, "status_service"):
            state = self.status_service.state(self)
            return state.ready, state.message
        if self.remote_check:
            return False, "Verifica SharePoint richiesta prima dell'avvio."
        return self.evaluate_requirements()

    def evaluate_requirements(self):
        if not self.script or not self.script.is_file():
            return False, "Funzione non ancora disponibile."
        if self.folder and self.filename:
            import fnmatch
            # iterdir surfaces access errors that Path.glob may silently suppress.
            matches = [f for f in self.folder.iterdir() if fnmatch.fnmatch(f.name, self.filename) and f.is_file()]
            count = len(matches)
            if self.expected_count > 1:
                if count == self.expected_count:
                    return True, f"Tutti i file richiesti sono presenti: {count}/{self.expected_count}."
                if count < self.expected_count:
                    return False, f"File presenti: {count}/{self.expected_count}. Ne mancano {self.expected_count - count}."
                return False, f"File presenti: {count}/{self.expected_count}. Rimuovi i file in eccesso."
            if matches:
                return True, f"File trovato: {matches[0].name}"
            return False, f"File richiesto non trovato: {self.filename}"
        return True, "Tutto pronto per l'esecuzione."

    def refresh_status(self):
        pass


class ActivityListButton(QPushButton):
    """Compact, keyboard-accessible row; Qt paints hover, selection and focus."""

    def __init__(self, activity, callback, parent=None, favorites=None):
        super().__init__(parent)
        self.activity = activity
        self.favorites = favorites
        self.star = role(QPushButton(self), "iconButton")
        self.star.setFixedSize(32, 32)
        self.star.clicked.connect(self.toggle_favorite)
        self.star.setVisible(favorites is not None)
        self.refresh_star()
        self.state_text = ""
        self.state_color = Theme.MUTED
        role(self, "activity")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(Theme.ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(0)
        self.row_icon = activity_icon(activity.activity_id)
        self.clicked.connect(lambda checked=False: callback(activity))
        self.refresh_text()

    def sizeHint(self):
        return QSize(320, Theme.ROW_HEIGHT)

    def minimumSizeHint(self):
        return QSize(180, Theme.ROW_HEIGHT)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.star.move(self.width() - 38, 21)

    def refresh_star(self):
        selected = bool(self.favorites and self.activity.activity_id in self.favorites.ids)
        self.star.setIcon(line_icon("star_filled" if selected else "star", "#C18B22"))
        label = "Rimuovi dai preferiti" if selected else "Aggiungi ai preferiti"
        self.star.setToolTip(label)
        self.star.setAccessibleName(f"{label}: {self.activity.title}")

    def toggle_favorite(self):
        try:
            self.favorites.toggle(self.activity.activity_id)
        except OSError:
            QMessageBox.warning(self, "Preferiti", "Impossibile salvare le preferenze. Controlla l'accesso alla cartella del profilo.")

    def refresh_text(self, running=False):
        ready, message = self.activity.readiness()
        if hasattr(self.activity, "status_service"):
            status = self.activity.status_service.state(self.activity)
            state = status.name
            color = {"Pronto": Theme.SUCCESS, "File mancanti": Theme.WARNING,
                     "Errore di verifica": "#B42332", "In esecuzione": Theme.INFO,
                     "Verifica in corso": Theme.INFO}.get(state, Theme.MUTED)
        elif running:
            state, color = "In esecuzione", Theme.INFO
        elif not self.activity.available:
            state, color = "Non disponibile", Theme.MUTED
        elif self.activity.remote_check:
            state, color = "Verifica SharePoint", Theme.INFO
        elif ready:
            state, color = "Pronto", Theme.SUCCESS
        else:
            state, color = "File mancanti", Theme.WARNING
        self.state_text, self.state_color = state, color
        self.setAccessibleName(f"{self.activity.title}. {self.activity.description}. {state}")
        self.setToolTip(f"{self.activity.title}\n{self.activity.description}\n{state}\n{message}")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        self.row_icon.paint(painter, QRect(10, 21, 32, 32))
        left, width = 52, max(1, self.width() - 96)
        for text, y, size, weight, color in (
            (self.activity.title, 8, 14, QFont.DemiBold, Theme.TEXT),
            (self.activity.description, 29, 12, QFont.Normal, Theme.MUTED),
            (self.state_text, 49, 11, QFont.Normal, self.state_color),
        ):
            font = QFont(Theme.FONT)
            font.setPixelSize(size)
            font.setWeight(weight)
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(QRect(left, y, width, 20), Qt.AlignLeft | Qt.AlignVCenter,
                             painter.fontMetrics().elidedText(text, Qt.ElideRight, width))
        if not self.isChecked():
            painter.setPen(QColor(Theme.BORDER))
            painter.drawLine(left, self.height() - 1, self.width() - 12, self.height() - 1)


class ActivityDetailPanel(QFrame):
    files_requested = Signal()
    add_files_requested = Signal()

    def __init__(self, parent=None, status_service=None):
        super().__init__(parent)
        self.activity = None
        self.busy = False
        self.running_activity = None
        self.status_service = status_service
        self.remote_checker = status_service.remote_checker
        status_service.changed.connect(self.refresh)
        self.setObjectName("detailPanel")
        self.setMinimumWidth(330)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("detailBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(Theme.PAD, 30, Theme.PAD, Theme.PAD)
        layout.setSpacing(16)
        self.category = role(QLabel("DETTAGLI ATTIVITÀ"), "eyebrow")
        self.activity_image = QLabel()
        self.activity_image.setFixedSize(44, 44)
        layout.addWidget(self.activity_image)
        self.title = role(QLabel("Seleziona un'attività"), "title")
        self.title.setWordWrap(True)
        self.description = role(QLabel("Scegli una voce dall'elenco."), "body")
        self.description.setWordWrap(True)
        layout.addWidget(self.category)
        layout.addWidget(self.title)
        layout.addWidget(self.description)
        divider = role(QFrame(), "separator")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        self.instructions_title = role(QLabel("Prima di iniziare"), "section")
        self.instructions = role(QLabel(), "body")
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions_title)
        layout.addWidget(self.instructions)
        layout.addSpacing(4)
        layout.addWidget(role(QLabel("Disponibilità"), "section"))
        self.status = role(QLabel("Nessuna attività selezionata."), "status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.requirements = role(QLabel(), "secondary")
        self.requirements.setWordWrap(True)
        layout.addWidget(self.requirements)
        self.folder = role(ElidedLabel(), "secondary")
        self.folder.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.folder)
        self.files_button = QPushButton("Gestisci file")
        self.files_button.setIcon(line_icon("files"))
        self.files_button.clicked.connect(self.files_requested.emit)
        layout.addWidget(self.files_button, alignment=Qt.AlignLeft)
        self.remote_check_button = QPushButton("Ripeti verifica SharePoint")
        self.remote_check_button.clicked.connect(self._check_remote)
        layout.addWidget(self.remote_check_button, alignment=Qt.AlignLeft)
        layout.addStretch()
        self.scroll.setWidget(body)
        root.addWidget(self.scroll, 1)
        footer = QFrame()
        footer.setObjectName("detailFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(Theme.PAD, 16, Theme.PAD, 20)
        footer_layout.setSpacing(8)
        self.action = role(QPushButton("Seleziona un'attività"), "primary")
        self.action.setCursor(Qt.PointingHandCursor)
        self.action.setMinimumHeight(40)
        self.action.setMinimumWidth(200)
        self.action.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.action.setEnabled(False)
        self.action.clicked.connect(self.run_or_prepare)
        footer_layout.addWidget(self.action, alignment=Qt.AlignLeft)
        hint = role(QLabel("L'avanzamento viene mostrato nel terminale."), "secondary")
        hint.setWordWrap(True)
        footer_layout.addWidget(hint)
        root.addWidget(footer)
        global_signals.script_avviato.connect(self._script_started)
        global_signals.script_terminato.connect(self._script_finished)
        self.set_activity(None)

    def set_activity(self, activity):
        changed = self.activity is not activity
        self.activity = activity
        self.activity_image.setVisible(activity is not None)
        if activity:
            self.activity_image.setPixmap(activity_icon(activity.activity_id).pixmap(QSize(44, 44)))
        self.category.setText(activity.category.upper() if activity else "DETTAGLI ATTIVITÀ")
        self.title.setText(activity.title if activity else "Nessun risultato")
        self.description.setText(activity.description if activity else "Prova con un'altra ricerca o scegli una sezione.")
        self.instructions.setText(
            (activity.instructions or "Nessun passaggio preliminare richiesto.") if activity else "")
        self.instructions_title.setVisible(activity is not None)
        self.instructions.setVisible(activity is not None)
        self.refresh()
        if changed:
            self.scroll.verticalScrollBar().setValue(0)

    @Slot()
    def _script_started(self):
        self.busy = True
        self.running_activity = getattr(getattr(self.window(), "execution", None), "current", self.activity)
        self.refresh()

    @Slot()
    def _script_finished(self):
        self.busy = False
        self.running_activity = None
        self.refresh()

    def refresh(self):
        activity = self.activity
        self.files_button.setVisible(bool(activity and activity.folder))
        self.folder.setVisible(bool(activity and activity.folder))
        self.requirements.setVisible(bool(activity and activity.filename))
        self.remote_check_button.setVisible(bool(activity and activity.remote_check))
        if not activity:
            self.status.setText("Nessuna attività selezionata.")
            set_tone(self.status, "muted")
            self.action.setText("Seleziona un'attività")
            self.action.setEnabled(False)
            self.folder.clear()
            self.requirements.clear()
            return
        ready, message = activity.readiness()
        state = self.status_service.state(activity)
        checking = state.name == "Verifica in corso" and (not activity.remote_check or self.remote_checker.running)
        if self.busy:
            message = f"In esecuzione: {self.running_activity.title if self.running_activity else 'attività'}. Attendi il completamento."
        self.status.setText(f"{state.name}: {message}")
        set_tone(self.status, "info" if self.busy or checking else
                 "ready" if ready else "warning" if activity.available else "muted")
        self.folder.setText(str(activity.folder) if activity.folder else "")
        self.requirements.setText(
            f"File richiesti: {activity.filename}\nQuantità attesa: {activity.expected_count}"
            if activity.filename else "")
        # Keep the lock across timer refreshes, searches and navigation.
        self.action.setEnabled(activity.available and not self.busy and not checking)
        self.remote_check_button.setEnabled(activity.available and not self.busy and not self.remote_checker.running)
        if self.busy:
            self.action.setText("Esecuzione in corso")
        elif not activity.available:
            self.action.setText("Non disponibile")
        elif checking:
            self.action.setText("Verifica in corso…")
        elif activity.remote_check and not ready:
            self.action.setText("Verifica SharePoint")
            self.action.setEnabled(not self.remote_checker.running)
        elif ready:
            self.action.setText("Esegui attività")
        else:
            self.action.setText("Aggiungi file richiesti")

    def _check_remote(self):
        if self.busy or not self.activity or not self.activity.available or self.remote_checker.running:
            return
        self.status_service.check_remote(self.activity)

    def run_or_prepare(self):
        activity = self.activity
        if self.busy or not activity or not activity.available:
            return
        ready, _ = activity.readiness()
        if activity.remote_check:
            if not ready:
                self._check_remote()
                return
        if not ready:
            self.add_files_requested.emit()
            self.refresh()
            return
        lancia_script(activity.script, activity.terminal)


class ModernHubPage(QWidget):
    def __init__(self, activities, parent=None, header=None, favorites=None, status_service=None):
        super().__init__(parent)
        self.activities = activities
        self.favorites = favorites
        if favorites:
            favorites.changed.connect(self.rebuild)
        self.current_filter = "today"
        self.buttons = []
        self.setObjectName("hub")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        list_panel = QFrame()
        list_panel.setObjectName("listPanel")
        list_panel.setMinimumWidth(340)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(Theme.PAD, Theme.PAD, 18, 16)
        list_layout.setSpacing(Theme.GAP)
        self.header = header or WorkspaceHeader()
        list_layout.addWidget(self.header)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Cerca attività")
        self.search.setAccessibleName("Cerca attività nella sezione")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(38)
        self.search.addAction(line_icon("search"), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self.rebuild)
        list_layout.addWidget(self.search)
        self.count_label = role(QLabel(), "secondary")
        list_layout.addWidget(self.count_label)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Native wheel scrolling plus touch scrolling without intercepting mouse clicks.
        QScroller.grabGesture(self.scroll.viewport(), QScroller.TouchGesture)
        self.list_body = QWidget()
        self.list_body.setObjectName("listBody")
        self.list_box = QVBoxLayout(self.list_body)
        self.list_box.setContentsMargins(0, 0, 0, 4)
        self.list_box.setSpacing(2)
        self.scroll.setWidget(self.list_body)
        list_layout.addWidget(self.scroll, 1)
        self.splitter.addWidget(list_panel)
        self.detail = ActivityDetailPanel(status_service=status_service)
        self.splitter.addWidget(self.detail)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([520, 520])
        root.addWidget(self.splitter)
        self.group = QButtonGroup(self)
        status_service.changed.connect(self.refresh_rows)
        global_signals.script_avviato.connect(self.refresh_rows)
        global_signals.script_terminato.connect(self.refresh_rows)
        self.rebuild()

    def set_filter(self, name):
        self.current_filter = name
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.rebuild()

    def visible_activities(self):
        query = self.search.text().strip().casefold()
        items = self.activities
        if self.current_filter == "today":
            by_id = {a.activity_id: a for a in items}
            items = [by_id[key] for key in self.favorites.ids if key in by_id]
        elif self.current_filter in ("business", "consumer", "campaigns"):
            category = "Campagne" if self.current_filter == "campaigns" else self.current_filter.title()
            items = [a for a in items if a.category == category]
        if query:
            items = [a for a in items if query in f"{a.title} {a.description} {a.category}".casefold()]
        return items

    def rebuild(self):
        selected = self.detail.activity
        position = self.scroll.verticalScrollBar().value()
        while self.list_box.count():
            item = self.list_box.takeAt(0)
            if item.widget():
                if isinstance(item.widget(), QPushButton):
                    self.group.removeButton(item.widget())
                item.widget().hide()
                item.widget().deleteLater()
        self.buttons = []
        items = self.visible_activities()
        self.count_label.setText(f"{len(items)} attività")
        for activity in items:
            button = ActivityListButton(activity, self.select_activity, favorites=self.favorites)
            self.buttons.append(button)
            self.group.addButton(button)
            self.list_box.addWidget(button)
        if not items:
            empty = role(QLabel("Nessuna attività trovata.\nCambia ricerca o aggiungi preferiti dalla sezione Tutte le attività."), "secondary")
            empty.setWordWrap(True)
            empty.setContentsMargins(12, 24, 12, 24)
            self.list_box.addWidget(empty)
        self.list_box.addStretch()
        kept_selection = any(activity is selected for activity in items)
        self.select_activity(selected if kept_selection else items[0] if items else None)
        self.scroll.verticalScrollBar().setValue(position if kept_selection else 0)
        self.refresh_rows()

    @Slot()
    def refresh_rows(self):
        for button in self.buttons:
            button.refresh_text(button.activity is self.detail.running_activity)

    def select_activity(self, activity):
        for button in self.buttons:
            button.setChecked(button.activity is activity)
            if button.activity is activity and button.hasFocus():
                self.scroll.ensureWidgetVisible(button, 0, 8)
        self.detail.set_activity(activity)


class FilesPage(QWidget):
    def __init__(self, paths, callback, parent=None):
        super().__init__(parent)
        self.setObjectName("filesPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.PAD, Theme.PAD, Theme.PAD, Theme.PAD)
        layout.setSpacing(Theme.GAP)
        layout.addWidget(role(QLabel("ARCHIVIO"), "eyebrow"))
        layout.addWidget(role(QLabel("File operativi"), "title"))
        subtitle = role(QLabel("Controlla, aggiungi o rimuovi i file usati dalle elaborazioni."), "body")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("fileBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 8, 0, 0)
        self.raw_files_widget = RawFilesWidget(paths["RAW_FILES"], on_folder_changed=callback)
        body_layout.addWidget(self.raw_files_widget)
        body_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)


class OperationsWindow(QMainWindow):
    def __init__(self, sharepoint_root, raw_files_path=None):
        super().__init__()
        self.sharepoint_root = Path(sharepoint_root)
        self.paths = _build_paths(self.sharepoint_root, Path(raw_files_path) if raw_files_path else None)
        os.environ["BASE_DIR"] = str(self.sharepoint_root)
        os.environ["MYWAY_SHAREPOINT_ROOT"] = str(self.sharepoint_root)
        self.setWindowTitle("MyWay Tools")
        self.setMinimumSize(1024, 640)
        self.resize(1400, 880)
        self.setWindowIcon(carica_icona())
        self.setStyleSheet(WORKSPACE_QSS)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = WorkspaceSidebar(self.show_page)
        root.addWidget(self.sidebar)
        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        self.header = WorkspaceHeader()
        self.terminal = TerminaleWidget()
        self.activities = self._build_activities()
        self.execution = ExecutionService(self.terminal, lambda: _trova_python(), self.activities, parent=self)
        self.terminal.execution_service = self.execution
        self.execution.started.connect(lambda activity: global_signals.script_avviato.emit())
        self.execution.finished.connect(lambda result: global_signals.script_terminato.emit())
        self.status_service = StatusService(self.activities, SharePointCheck(self), parent=self)
        for activity in self.activities:
            activity.status_service = self.status_service
        self.execution.status_service = self.status_service
        self.execution.started.connect(self.status_service.started)
        self.execution.finished.connect(self.status_service.finished)
        self.favorites = Favorites([a.activity_id for a in self.activities], parent=self)
        self.hub = ModernHubPage(self.activities, header=self.header, favorites=self.favorites,
                                 status_service=self.status_service)
        if self.favorites.warning:
            self.terminal.write_safe(self.favorites.warning + "\n", C_LOG_WARN)
        self.files_page = FilesPage(self.paths, self.set_raw_folder)
        self.hub.detail.files_requested.connect(lambda: self.show_page("files"))
        self.hub.detail.add_files_requested.connect(self.files_page.raw_files_widget._carica_file)
        self.status_service.watcher.directoryChanged.connect(lambda _: self.files_page.raw_files_widget._aggiorna_lista())
        self.pages = QStackedWidget()
        self.pages.addWidget(self.hub)
        self.pages.addWidget(self.files_page)
        self.history_page = HistoryPage(self.execution.history, self.activities)
        self.pages.addWidget(self.history_page)
        self.workflow_store = WorkflowStore([a.activity_id for a in self.activities])
        self.workflow_manager = WorkflowManager(self.execution, self.activities, parent=self)
        self.workflow_page = ManagedWorkflowPage(self.workflow_store, self.workflow_manager, self.activities)
        self.pages.addWidget(self.workflow_page)
        self.summary_page = SummaryDashboard(self.execution.history, self.show_page)
        self.pages.addWidget(self.summary_page)
        self.execution.finished.connect(self.summary_page.refresh)
        self.history_page.history_cleared.connect(self.summary_page.refresh)
        self.history_page.history_cleared.connect(self.workflow_page.load_recent)
        self.workflow_manager.changed.connect(self._execution_changed)
        self.workflow_manager.finished.connect(lambda _: self.terminal.state.setText("Pronto"))
        self.execution.finished.connect(self.history_page.refresh)
        self.terminal.btn_stop = QPushButton("Interrompi")
        self.terminal.btn_stop.setEnabled(False)
        self.terminal.layout().itemAt(0).widget().layout().insertWidget(3, self.terminal.btn_stop)
        self.terminal.btn_stop.clicked.connect(self.stop_execution)
        self.execution.changed.connect(self._execution_changed)
        self.splitter = QSplitter(Qt.Vertical)
        self.pages.setMinimumHeight(280)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(4)
        self.splitter.addWidget(self.pages)
        self.splitter.addWidget(self.terminal)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([650, 210])
        self.terminal.set_collapsed(True)
        workspace_layout.addWidget(self.splitter, 1)
        root.addWidget(workspace, 1)
        self.show_page("today")
        self.showMaximized()

    def closeEvent(self, event):
        if self.execution.busy or self.workflow_manager.active:
            answer = QMessageBox.question(self, "Attività in corso",
                "Interrompere l'attività e chiudere al termine dell'arresto?")
            event.ignore()
            if answer == QMessageBox.Yes:
                if not getattr(self, "_closing", False):
                    self._closing = True
                    signal = self.workflow_manager.finished if self.workflow_manager.active else self.execution.finished
                    signal.connect(lambda result: QTimer.singleShot(0, self.close))
                self.stop_execution()
            return
        super().closeEvent(event)

    def stop_execution(self):
        if self.workflow_manager.active:
            self.workflow_manager.cancel()
        else:
            self.execution.cancel()

    def _execution_changed(self):
        busy = self.execution.busy or self.workflow_manager.active
        self.terminal.btn_stop.setEnabled(busy)
        self.hub.detail.busy = busy
        self.hub.detail.running_activity = self.execution.current
        self.hub.detail.refresh()
        if self.workflow_manager.active:
            self.terminal.state.setText("Workflow in corso")

    def _build_activities(self):
        p = self.paths
        rows = [
            ("Estrai file gara", "Estrae, formatta e pubblica gara, opportunità e appuntamenti.", "Business", p["ESTRAI_FILE_GARA"]),
            ("Forecast Business", "Genera il forecast giornaliero e la reportistica associata.", "Business", p["FCST"]),
            ("Appuntamenti settimanali", "Prepara il report settimanale per ciascun venditore.", "Business", p["APPUNTAMENTI_SETTIMANA"]),
            ("Performance Management CRM", "Genera le anteprime giornaliere delle azioni CRM da completare per ciascun commerciale.", "Business", p["PERFORMANCE_MANAGEMENT_CRM"]),
            ("Elabora CB", "Analizza consistenze, anagrafiche e produce il report CB.", "Business", p["ELABORA_CB"], None, None, "Inserisci la nuova CB in 00_SCAMBIO_DOCUMENTI > 00_BUSINESS > CB > 00_DA_ELABORARE.", "sharepoint_cb"),
            ("Formatta pedonalità", "Prepara il file pedonalità per le elaborazioni.", "Consumer", p["FORMATTA_PEDONALITA"], p["RAW_FILES"], "Giorgio Mandelli*.xlsx", "Scarica il file dal portale Vodafone e inseriscilo nella cartella RAW_FILE."),
            ("Cruscotto tracciamento", "Aggrega Business, Energia e Gadget per il monitoraggio negozi.", "Consumer", p["CRUSCOTTO_TRACCIAMENTO"]),
            ("Cruscotto giornaliero", "Riunisce le piste Consumer nel report operativo quotidiano.", "Consumer", p["CRUSCOTTO_GIORNALIERO"], p["RAW_FILES"], "*AVANZAMENTI*.xls*", "Scarica da StoreSales i cinque report PEZZI e i cinque report PUNTI, rinominali e inseriscili nella cartella RAW_FILE.", None, 10),
            ("Giacenze smartphone", "Genera il report aggiornato delle giacenze smartphone.", "Consumer", p["REPORT_GIACENZE_SMARTPHONE"], p["RAW_FILES"], "*GIACENZE_ARTICOLI*.xls*", "Scarica da StoreSales il report Giacenze Articoli filtrato su TELEFONIA > SMARTPHONE."),
            ("Divisione per agente", "Divide i file campagna e li assegna ai venditori.", "Campagne", p["DIVIDI_FILE_CAMPAGNE"]),
            ("Riaggrega file", "Ricompone i file lavorati dai venditori.", "Campagne", p["AGGREGA_FILE_VENDITORI"]),
            ("Presa in carico", "Controlla le lavorazioni e assegna i clienti al CRM.", "Campagne", p["PRESA_IN_CARICO"]),
            ("Report campagne", "Statistiche, KPI ed esiti delle campagne.", "Campagne", p["REPORT_CAMPAGNE"]),
            ("Formatta gara", "Elabora lo storico gara estratto dal CRM.", "Business", p["FORMATTA_GARA"]),
            ("Formatta appuntamenti", "Prepara il file appuntamenti estratto dal CRM.", "Business", p["FORMATTA_APPUNTAMENTI"]),
            ("Formatta opportunità", "Prepara il file opportunità estratto dal CRM.", "Business", p["FORMATTA_OPPORTUNITA"]),
            ("Chiusura gara", "Estrae gli ordini attivati nella gara precedente.", "Business", p["CHIUSURA_GARA"]),
            ("Report pedonalità", "Crea il report di analisi dei flussi nei punti vendita.", "Consumer", p["REPORT_PEDONALITA"]),
            ("Formatta magazzino", "Classifica e prepara il file valore del magazzino.", "Consumer", p["FORMATTA_MAGAZZINO"], p["RAW_FILES"], "VALORE_DEL_MAGAZZINO*.csv"),
        ]
        activities = []
        # IDs are permanent domain keys, independent of display order and titles.
        ids_by_script_key = {
            "ESTRAI_FILE_GARA": "estrai_file_gara", "FCST": "forecast_business",
            "APPUNTAMENTI_SETTIMANA": "appuntamenti_settimanali", "PERFORMANCE_MANAGEMENT_CRM": "performance_management_crm",
            "ELABORA_CB": "elabora_cb",
            "FORMATTA_PEDONALITA": "formatta_pedonalita", "CRUSCOTTO_TRACCIAMENTO": "cruscotto_tracciamento",
            "CRUSCOTTO_GIORNALIERO": "cruscotto_giornaliero", "REPORT_GIACENZE_SMARTPHONE": "giacenze_smartphone",
            "DIVIDI_FILE_CAMPAGNE": "dividi_file_campagne", "AGGREGA_FILE_VENDITORI": "aggrega_file_venditori",
            "PRESA_IN_CARICO": "presa_in_carico", "REPORT_CAMPAGNE": "report_campagne",
            "FORMATTA_GARA": "formatta_gara", "FORMATTA_APPUNTAMENTI": "formatta_appuntamenti",
            "FORMATTA_OPPORTUNITA": "formatta_opportunita", "CHIUSURA_GARA": "chiusura_gara",
            "REPORT_PEDONALITA": "report_pedonalita", "FORMATTA_MAGAZZINO": "formatta_magazzino",
        }
        ids_by_path = {p[key]: value for key, value in ids_by_script_key.items()}
        for i, row in enumerate(rows, 1):
            title, description, category, script, *options = row
            options += [None] * (5 - len(options))
            folder, filename, instructions, remote_check, expected_count = options[:5]
            activities.append(ActivitySpec(
                i, title, description, category, script, self.terminal,
                folder, filename, instructions or "", remote_check, expected_count or 1,
                ids_by_path[script]))
        return activities

    def show_page(self, name):
        self.sidebar.select(name)
        if name == "summary":
            self.pages.setCurrentWidget(self.summary_page)
            self.summary_page.refresh()
            return
        if name == "workflows":
            self.pages.setCurrentWidget(self.workflow_page)
            self.workflow_page.refresh()
            self.workflow_page.load_recent()
            return
        if name == "history":
            self.pages.setCurrentWidget(self.history_page)
            self.history_page.refresh()
            return
        if name == "files":
            self.pages.setCurrentWidget(self.files_page)
            self.files_page.raw_files_widget._aggiorna_lista()
            self.header.set_page("Archivio", "File", "Input e cartella di lavoro.")
            return
        self.pages.setCurrentWidget(self.hub)
        self.hub.set_filter(name)
        titles = {
            "today": ("Hub", "Oggi", "Le attività operative più frequenti."),
            "all": ("Hub", "Tutte le attività", "Cerca e avvia qualsiasi procedura."),
            "business": ("Area", "Business", "Procedure e reportistica Business."),
            "consumer": ("Area", "Consumer", "Procedure e reportistica Consumer."),
            "campaigns": ("Area", "Campagne", "Gestione completa delle campagne."),
        }
        self.header.set_page(*titles[name])

    def set_raw_folder(self, folder):
        folder = Path(folder)
        self.paths["RAW_FILES"] = folder
        salva_cartella_raw(folder, self.sharepoint_root)
        for activity in self.activities:
            if activity.filename:
                activity.folder = folder
        self.status_service.raw_changed()
        self.hub.rebuild()


# ─────────────────────────────────────────────────────────────
# AVVIO
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(carica_icona())
    app.setStyleSheet("""
        QWidget { font-family: "Segoe UI"; }
        QToolTip { background:#111827; color:white; border:none; padding:5px; }
        QScrollBar:vertical { background:transparent; width:9px; margin:2px; }
        QScrollBar::handle:vertical { background:#C9CFD8; border-radius:4px; min-height:32px; }
        QScrollBar::handle:vertical:hover { background:#AAB2BE; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
    """)

    # ── Carica config PRIMA dello splash ──────────────────────
    config = carica_config()

    if config is None:
        messaggio = (
            "La cartella RAW_FILES non è configurata o non è raggiungibile."
            if CONFIG_PATH.exists()
            else ""
        )
        dlg = ConfigDialog(messaggio)
        if dlg.exec() != QDialog.Accepted or dlg.sharepoint_root is None:
            sys.exit(0)
        sharepoint_root = dlg.sharepoint_root
        raw_files_path = dlg.raw_files_path
    else:
        raw_value = config.get("raw_files_path")
        raw_files_path = Path(raw_value) if raw_value else None
        root_value = config.get("sharepoint_root")
        sharepoint_root = Path(root_value) if root_value else raw_files_path.parent

    prepara_env_locale(sharepoint_root)

    # Mostra subito la finestra: nessun ritardo artificiale.
    window = OperationsWindow(sharepoint_root, raw_files_path)

    # Il controllo aggiornamenti resta asincrono e parte dopo il primo render.
    QTimer.singleShot(800, lambda: (
        __import__('updater').check_and_update(app)
    ))

    sys.exit(app.exec())
