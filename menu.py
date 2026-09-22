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
from updater import get_asset

from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QScrollArea, QTextEdit,
    QSizePolicy, QStackedWidget, QGridLayout, QSpacerItem, QSplitter,
    QFileDialog, QMessageBox, QSplashScreen, QDialog,
    QDialogButtonBox, QLineEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QSize
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self.setMinimumHeight(32)
        self.setStyleSheet(f"background:{C_LOG_BG}; border:none;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(32)
        header.setStyleSheet("background:#222222; border:none;")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(8, 0, 8, 0)

        lbl = QLabel("  ◉  TERMINALE")
        lbl.setStyleSheet(f"color:{C_LOG_OK}; font-family:Courier; font-size:12px; font-weight:bold; background:transparent;")
        h_lay.addWidget(lbl)
        h_lay.addStretch()

        btn_toggle = QPushButton("Nascondi")
        btn_toggle.setFixedSize(76, 22)
        btn_toggle.setStyleSheet("""
            QPushButton { background:#333333; color:#B8BDC7; border:none;
                          border-radius:4px; font-size:11px; }
            QPushButton:hover { background:#444444; color:white; }
        """)
        btn_toggle.clicked.connect(lambda: self._toggle(btn_toggle))
        h_lay.addWidget(btn_toggle)

        btn_pulisci = QPushButton("Pulisci")
        btn_pulisci.setFixedSize(70, 22)
        btn_pulisci.setStyleSheet("""
            QPushButton { background:#333333; color:#888888; border:none;
                          border-radius:4px; font-size:11px; }
            QPushButton:hover { background:#444444; }
        """)
        btn_pulisci.clicked.connect(self.pulisci)
        h_lay.addWidget(btn_pulisci)
        layout.addWidget(header)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(f"""
            QTextEdit {{
                background:{C_LOG_BG}; color:{C_LOG_TEXT};
                font-family:Courier; font-size:13px;
                border:none; padding:4px 8px;
            }}
        """)
        layout.addWidget(self.log)

        self.signals = LogSignals()
        self.signals.append.connect(self._append_colored)
        self._write("Pronto. Avvia uno script per vedere l'output qui.\n", C_LOG_INFO)

    def _append_colored(self, testo, colore):
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colore))
        cursor.insertText(testo, fmt)
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    def _write(self, testo, colore):
        self._append_colored(testo, colore)

    def write_safe(self, testo, colore):
        self.signals.append.emit(testo, colore)

    def pulisci(self):
        self.log.clear()

    def _toggle(self, button):
        self._collapsed = not self._collapsed
        self.log.setVisible(not self._collapsed)
        splitter = self.parentWidget()
        if isinstance(splitter, QSplitter):
            total = max(sum(splitter.sizes()), 400)
            terminal_height = 32 if self._collapsed else 190
            splitter.setSizes([max(1, total - terminal_height), terminal_height])
        button.setText("Mostra" if self._collapsed else "Nascondi")


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
    script_path = Path(nome_script).resolve()

    terminale.write_safe("\n", C_LOG_INFO)
    terminale.write_safe(f"Avvio: {script_path.name}\n", C_LOG_TEXT)
    terminale.write_safe("─" * 60 + "\n", "#333333")

    if not script_path.is_file():
        terminale.write_safe(f"❌ File non trovato: {script_path}\n", C_LOG_ERR)
        terminale.write_safe("─" * 60 + "\n", "#333333")
        if on_finished:
            on_finished(False)
        return

    def _run():
        python_exe = _trova_python()
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        bootstrap = (
            "import runpy, sys; "
            "from pathlib import Path; "
            "script = sys.argv[1]; "
            "sys.argv = sys.argv[1:]; "
            "sys.path.insert(0, str(Path(script).resolve().parent)); "
            "runpy.run_path(script, run_name='__main__')"
        )

        try:
            process = subprocess.Popen(
                [python_exe, "-u", "-c", bootstrap, str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                env=env, cwd=str(script_path.parent),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            for riga in process.stdout:
                riga_pulita = rimuovi_ansi(riga.rstrip("\n").rstrip("\r"))
                if riga_pulita.strip():
                    terminale.write_safe(riga_pulita + "\n", colore_riga(riga_pulita))
            process.wait()
            if process.returncode == 0:
                terminale.write_safe("\n✅ Completato con successo.\n", C_LOG_OK)
                terminale.write_safe("─" * 60 + "\n", "#333333")
                if on_finished: on_finished(True)
            else:
                terminale.write_safe(f"\n❌ Script terminato con errore (exit {process.returncode}).\n", C_LOG_ERR)
                terminale.write_safe("─" * 60 + "\n", "#333333")
                if on_finished: on_finished(False)

        except FileNotFoundError:
            terminale.write_safe(f"❌ Python runtime non trovato: {python_exe}\n", C_LOG_ERR)
            if on_finished: on_finished(False)
        except Exception as ex:
            import traceback
            terminale.write_safe(f"\n❌ Eccezione: {ex}\n", C_LOG_ERR)
            terminale.write_safe(traceback.format_exc() + "\n", C_LOG_ERR)
            if on_finished: on_finished(False)

    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────
# SCRIPT CARD
# ─────────────────────────────────────────────────────────────
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
        global_signals.script_avviato.emit()
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
        global_signals.script_terminato.emit()

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
        self.setStyleSheet(f"RawFilesWidget {{ background:{C_PANEL}; border-radius:14px; border:1px solid {C_BORDER}; }}")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(190)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(11)

        header_row = QHBoxLayout()
        icona = QLabel("📁")
        icona.setStyleSheet(f"font-size:27px; color:{C_RED}; background:transparent; border:none;")
        header_row.addWidget(icona)
        lbl_titolo = QLabel("Raw Files")
        lbl_titolo.setStyleSheet(f"font-size:17px; font-weight:bold; color:{C_TEXT_DARK}; background:transparent; border:none;")
        header_row.addWidget(lbl_titolo)
        header_row.addStretch()
        self.lbl_count = QLabel("0 file")
        self.lbl_count.setStyleSheet(f"background:{C_RED}; color:white; border-radius:10px; font-size:12px; font-weight:bold; padding:2px 10px; border:none;")
        header_row.addWidget(self.lbl_count)
        btn_cartella = QPushButton("Cambia cartella")
        btn_cartella.setCursor(Qt.PointingHandCursor)
        btn_cartella.setStyleSheet(f"""
            QPushButton {{ background:{C_FASTWEB}; color:#111827; border:none; border-radius:7px;
                           font-size:13px; font-weight:bold; padding:6px 14px; }}
            QPushButton:hover {{ background:{C_FASTWEB_HOVER}; }}
        """)
        btn_cartella.clicked.connect(self._scegli_cartella)
        header_row.addWidget(btn_cartella)
        btn_carica = QPushButton("+ Carica file")
        btn_carica.setStyleSheet(f"""
            QPushButton {{ background:{C_RED}; color:white; border:none; border-radius:7px; font-size:13px; font-weight:bold; padding:6px 14px; }}
            QPushButton:hover {{ background:{C_RED_HOVER}; }}
        """)
        btn_carica.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_carica.clicked.connect(self._carica_file)
        header_row.addWidget(btn_carica)
        outer.addLayout(header_row)

        self.lbl_percorso = QLabel()
        self.lbl_percorso.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_percorso.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:11px; padding:0 2px;")
        self.lbl_percorso.setToolTip(str(self.cartella))
        outer.addWidget(self.lbl_percorso)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C_BORDER}; border:none;")
        outer.addWidget(sep)

        self.lista_frame = QFrame()
        self.lista_frame.setStyleSheet("background:transparent; border:none;")
        self.lista_layout = QVBoxLayout(self.lista_frame)
        self.lista_layout.setContentsMargins(0, 0, 0, 0)
        self.lista_layout.setSpacing(4)
        outer.addWidget(self.lista_frame)

        self.lbl_vuoto = QLabel("Nessun file presente. Carica i file raw da processare.")
        self.lbl_vuoto.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:13px; background:transparent; border:none; padding:12px 0;")
        self.lbl_vuoto.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.lbl_vuoto)

        hint = QLabel("Trascina i file qui oppure usa il pulsante  →  Carica file")
        hint.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:12px; background:transparent; border:1.5px dashed {C_BORDER}; border-radius:8px; padding:10px;")
        hint.setAlignment(Qt.AlignCenter)
        outer.addWidget(hint)

        self.setAcceptDrops(True)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._aggiorna_lista)
        self._timer.start(3000)
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
            self.setStyleSheet(f"RawFilesWidget {{ background:#FFF8F8; border-radius:14px; border:2px solid {C_RED}; }}")

    def dragLeaveEvent(self, e):
        self.setStyleSheet(f"RawFilesWidget {{ background:{C_PANEL}; border-radius:14px; border:1px solid {C_BORDER}; }}")

    def dropEvent(self, e):
        self.setStyleSheet(f"RawFilesWidget {{ background:{C_PANEL}; border-radius:14px; border:1px solid {C_BORDER}; }}")
        if e.mimeData().hasUrls():
            self._copia_files([Path(u.toLocalFile()) for u in e.mimeData().urls()])

    def _leggi_files(self):
        if not self.cartella.exists(): return []
        return sorted(
            (f for f in self.cartella.glob("*")
             if f.is_file() and f.name not in self._ESCLUDI and not f.name.startswith(".")),
            key=lambda f: f.name.lower()
        )

    def _aggiorna_lista(self, force=False):
        files = self._leggi_files()
        self.lbl_percorso.setText(f"Cartella attiva:  {self.cartella}")
        self.lbl_count.setText(f"{len(files)} file" if len(files) != 1 else "1 file")
        nomi_attuali = {
            self.lista_layout.itemAt(i).widget().property("nome_file")
            for i in range(self.lista_layout.count())
            if self.lista_layout.itemAt(i).widget()
        }
        if not force and nomi_attuali == {f.name for f in files}: return
        while self.lista_layout.count():
            item = self.lista_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for fpath in files:
            self.lista_layout.addWidget(self._crea_riga(fpath))
        self.lbl_vuoto.setVisible(len(files) == 0)
        self.lista_frame.setVisible(len(files) > 0)

    def _crea_riga(self, fpath: Path) -> QFrame:
        riga = QFrame()
        riga.setProperty("nome_file", fpath.name)
        riga.setFixedHeight(42)
        riga.setStyleSheet(f"QFrame {{ background:#FAFAFA; border-radius:8px; border:1px solid {C_BORDER}; }} QFrame:hover {{ background:{C_RED_LIGHT}; border:1px solid {C_RED}; }}")
        lay = QHBoxLayout(riga)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(10)
        ext = fpath.suffix.lower()
        ico = "📊" if ext in (".xlsx", ".xls") else "📋" if ext == ".csv" else "📄"
        lbl_ico = QLabel(ico)
        lbl_ico.setStyleSheet("font-size:16px; background:transparent; border:none;")
        lbl_ico.setFixedWidth(22)
        lay.addWidget(lbl_ico)
        lbl_nome = QLabel(fpath.name)
        lbl_nome.setStyleSheet(f"font-size:13px; font-weight:bold; color:{C_TEXT_DARK}; background:transparent; border:none;")
        lbl_nome.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(lbl_nome)
        try:    size_str = formatta_dimensione(fpath.stat().st_size)
        except: size_str = "—"
        lbl_size = QLabel(size_str)
        lbl_size.setStyleSheet(f"font-size:12px; color:{C_TEXT_LIGHT}; background:transparent; border:none;")
        lbl_size.setFixedWidth(60)
        lbl_size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(lbl_size)
        btn_del = QPushButton("❌")
        btn_del.setFixedSize(24, 24)
        btn_del.setStyleSheet(f"QPushButton {{ background:transparent; color:{C_TEXT_LIGHT}; border:1px solid {C_BORDER}; border-radius:5px; font-size:12px; }} QPushButton:hover {{ background:#FFECEC; color:{C_RED}; border:1px solid {C_RED}; }}")
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
            ("Business",          ["Estrai file gara", "FCST", "Appuntamenti"]),
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
        ]
        grid.setRowMinimumHeight(row, CARD_HEIGHT_STATUS + 16)
        for i, cfg in enumerate(cards_business):
            card = ScriptCard(cfg["icona"], cfg["titolo"], cfg["desc"], cfg["script"], terminale,
                              cartella=cfg.get("cartella"), nomi_file=cfg.get("nomi_file"))
            wrapper = QWidget(); wrapper.setStyleSheet("background:transparent;")
            w_lay = QVBoxLayout(wrapper); w_lay.setContentsMargins(0 if i == 0 else 8, 0, 0 if i == len(cards_business)-1 else 8, 0); w_lay.setSpacing(0)
            w_lay.addWidget(card, alignment=Qt.AlignTop)
            grid.addWidget(wrapper, row, i * 4, 1, 4)
        row += 1
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
        super().__init__(f"{icon}   {text}", parent)
        self.page = page
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        self.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:#CBD1DB; border:none;
                border-radius:9px; padding:0 16px; text-align:left;
                font-size:15px; font-weight:bold;
            }}
            QPushButton:hover {{ background:#202C3D; color:white; }}
            QPushButton:checked {{ background:{C_FASTWEB}; color:#111827; }}
        """)
        self.clicked.connect(lambda checked=False: callback(page))


class WorkspaceSidebar(QFrame):
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self.setStyleSheet(f"background:{C_SIDEBAR}; border:none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 18)
        layout.setSpacing(6)

        brand = QFrame()
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(8, 24, 8, 24)
        if ICON_PATH.exists():
            icon = QLabel()
            icon.setPixmap(QPixmap(str(ICON_PATH)).scaled(
                34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            brand_layout.addWidget(icon)
        title_box = QVBoxLayout()
        title = QLabel("MYWAY")
        title.setStyleSheet("color:white; font-size:18px; font-weight:bold;")
        subtitle = QLabel("OPERATIONS HUB")
        subtitle.setStyleSheet(f"color:{C_FASTWEB}; font-size:10px; font-weight:bold;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        brand_layout.addLayout(title_box)
        brand_layout.addStretch()
        layout.addWidget(brand)

        label = QLabel("  AREA DI LAVORO")
        label.setStyleSheet("color:#778295; font-size:10px; font-weight:bold; padding:8px 0;")
        layout.addWidget(label)

        self.buttons = {}
        for icon, text, page in (
            ("⌂", "Panoramica", "dashboard"),
            ("▶", "Giornalieri", "operations"),
            ("◆", "Campagne", "campaigns"),
            ("✦", "Utilità", "tools"),
        ):
            button = WorkspaceNavButton(icon, text, page, callback)
            self.buttons[page] = button
            layout.addWidget(button)

        layout.addStretch()
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#293548;")
        layout.addWidget(line)
        info = QLabel("FASTWEB + VODAFONE\nAutomazioni operative")
        info.setStyleSheet("color:#8E98A8; font-size:11px; padding:10px 8px;")
        layout.addWidget(info)
        exit_button = QPushButton("Esci")
        exit_button.setCursor(Qt.PointingHandCursor)
        exit_button.setFixedHeight(38)
        exit_button.setStyleSheet("""
            QPushButton { color:#CBD1DB; background:transparent; border:none;
                          border-radius:8px; text-align:left; padding-left:10px; font-size:13px; }
            QPushButton:hover { color:white; background:#202C3D; }
        """)
        exit_button.clicked.connect(QApplication.quit)
        layout.addWidget(exit_button)

    def select(self, page):
        for name, button in self.buttons.items():
            button.setChecked(name == page)


class WorkspaceHeader(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(92)
        self.setStyleSheet(f"background:{C_PANEL}; border:none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 14, 32, 12)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.eyebrow = QLabel("PANORAMICA")
        self.eyebrow.setStyleSheet(f"color:{C_RED}; font-size:10px; font-weight:bold;")
        self.title = QLabel("Centro operativo")
        self.title.setStyleSheet(f"color:{C_TEXT_DARK}; font-size:27px; font-weight:bold;")
        self.subtitle = QLabel("Tutto ciò che serve, senza passaggi superflui.")
        self.subtitle.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:13px;")
        text.addWidget(self.eyebrow)
        text.addWidget(self.title)
        text.addWidget(self.subtitle)
        layout.addLayout(text)
        layout.addStretch()
        self.clock = QLabel()
        self.clock.setStyleSheet(f"color:{C_TEXT_MID}; font-size:13px; font-weight:bold;")
        layout.addWidget(self.clock)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(30000)
        self.update_clock()

    def update_clock(self):
        self.clock.setText(datetime.now().strftime("%d %b %Y  ·  %H:%M"))

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
        global_signals.script_avviato.emit()
        lancia_script(self.script, self.terminal, self.signals.script_finished.emit)

    def finished(self, success):
        self.running = False
        self.status.setText("Completato correttamente" if success else "Terminato con errore")
        self.status.setStyleSheet(
            f"color:{C_LOG_OK if success else C_LOG_ERR}; font-size:11px; font-weight:bold;")
        global_signals.script_terminato.emit()

    def lock(self):
        if not self.running:
            self.run_button.setEnabled(False)

    def unlock(self):
        if not self.running:
            self.run_button.setText("Avvia" if self.available else "Non disponibile")
            self.refresh_status()


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
            self.remote_check_signals.finished.emit(*result)

        threading.Thread(target=check_cb, daemon=True).start()

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
        global_signals.script_avviato.emit()
        lancia_script(
            self.tile.script, self.tile.terminal,
            lambda success: global_signals.script_terminato.emit())


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


class OperationsWindow(QMainWindow):
    def __init__(self, sharepoint_root, raw_files_path=None):
        super().__init__()
        self.sharepoint_root = Path(sharepoint_root)
        self.paths = _build_paths(
            self.sharepoint_root, Path(raw_files_path) if raw_files_path else None)
        os.environ["BASE_DIR"] = str(self.sharepoint_root)
        os.environ["MYWAY_SHAREPOINT_ROOT"] = str(self.sharepoint_root)
        self.setWindowTitle("MyWay Operations Hub")
        self.setMinimumSize(1040, 680)
        self.resize(1360, 860)
        self.setWindowIcon(carica_icona())

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = WorkspaceSidebar(self.show_page)
        root.addWidget(self.sidebar)

        workspace = QWidget()
        workspace.setStyleSheet(f"background:{C_BG};")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        self.header = WorkspaceHeader()
        workspace_layout.addWidget(self.header)
        self.terminal = TerminaleWidget()
        self.pages = QStackedWidget()
        self.pages.setStyleSheet(f"background:{C_BG};")
        self.page_map = {}
        self._build_pages()

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(5)
        self.splitter.setStyleSheet(f"QSplitter::handle {{ background:#DCE1E8; }} QSplitter::handle:hover {{ background:{C_FASTWEB}; }}")
        self.splitter.addWidget(self.pages)
        self.splitter.addWidget(self.terminal)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([670, 190])
        workspace_layout.addWidget(self.splitter, stretch=1)
        root.addWidget(workspace, stretch=1)
        self.show_page("dashboard")
        self.showMaximized()

    def _build_pages(self):
        p = self.paths
        operations = [
            ("Business", [
                ("Estrai file gara", "Estrae, formatta e pubblica gara, opportunità e appuntamenti.", p["ESTRAI_FILE_GARA"]),
                ("Forecast Business", "Genera il forecast giornaliero e la reportistica associata.", p["FCST"]),
                ("Appuntamenti settimanali", "Prepara il report settimanale per ciascun venditore.", p["APPUNTAMENTI_SETTIMANA"]),
                ("Elabora CB", "Analizza consistenze, anagrafiche e produce il report CB.",
                 p["ELABORA_CB"], None, None,
                 "Una volta ricevuto il file della nuova CB, controlla la corretta assegnazione "
                 "dei venditori e inserisci il file nella cartella 00_SCAMBIO_DOCUMENTI > "
                 "00_BUSINESS > CB > 00_DA_ELABORARE. Lo script è quindi pronto per essere lanciato.",
                 "sharepoint_cb"),
            ]),
            ("Consumer", [
                ("Formatta pedonalità", "Prepara il file pedonalità per le elaborazioni.",
                 p["FORMATTA_PEDONALITA"], p["RAW_FILES"], "Giorgio Mandelli*.xlsx",
                 "Accedi al portale Vodafone dedicato e richiedi la mail con il link per scaricare "
                 "il file relativo alla pedonalità. Una volta ricevuta la mail, scarica il file e "
                 "inseriscilo all'interno della cartella RAW_FILE."),
                ("Cruscotto tracciamento", "Aggrega Business, Energia e Gadget per il monitoraggio negozi.", p["CRUSCOTTO_TRACCIAMENTO"]),
                ("Cruscotto giornaliero", "Riunisce le piste Consumer nel report operativo quotidiano.",
                 p["CRUSCOTTO_GIORNALIERO"], p["RAW_FILES"], "*AVANZAMENTI*.xls*",
                 "Accedi a StoreSales e apri ANALISI > Avanzamenti Vendite. Scarica i file "
                 "1.1, 1.2, 1.3, 2 e 3 selezionando PEZZI, quindi aggiungi _PEZZI alla fine "
                 "del nome di ciascun file. Ripeti la stessa procedura selezionando PUNTI e "
                 "aggiungi _PUNTI alla fine del nome di ciascun file. Una volta completato, "
                 "inserisci tutti e 10 i file nella cartella RAW_FILE.",
                 None, 10),
                ("Giacenze smartphone", "Genera il report aggiornato delle giacenze smartphone.",
                 p["REPORT_GIACENZE_SMARTPHONE"], p["RAW_FILES"], "*GIACENZE_ARTICOLI*.xls*",
                 "Accedi a StoreSales e apri MAGAZZINO > Giacenze Articoli. "
                 "Nel filtro CATEGORIE seleziona TELEFONIA > SMARTPHONE; nel campo VISUALIZZA "
                 "seleziona «solo in giacenza». Apri il report e scarica il file XLS."),
            ]),
        ]
        campaigns = [("Campagne", [
            ("Divisione per agente", "Divide i file campagna e li assegna ai venditori.", p["DIVIDI_FILE_CAMPAGNE"]),
            ("Riaggrega file", "Ricompone i file lavorati dai venditori.", p["AGGREGA_FILE_VENDITORI"]),
            ("Presa in carico", "Controlla le lavorazioni e assegna i clienti al CRM.", p["PRESA_IN_CARICO"]),
            ("Report campagne", "Statistiche, KPI ed esiti delle campagne.", p["REPORT_CAMPAGNE"]),
        ])]
        tools = [
            ("Business", [
                ("Formatta gara", "Elabora lo storico gara estratto dal CRM.", p["FORMATTA_GARA"]),
                ("Formatta appuntamenti", "Prepara il file appuntamenti estratto dal CRM.", p["FORMATTA_APPUNTAMENTI"]),
                ("Formatta opportunità", "Prepara il file opportunità estratto dal CRM.", p["FORMATTA_OPPORTUNITA"]),
                ("Chiusura gara", "Estrae gli ordini attivati nella gara precedente.", p["CHIUSURA_GARA"]),
            ]),
            ("Consumer", [
                ("Report pedonalità", "Crea il report di analisi dei flussi nei punti vendita.", p["REPORT_PEDONALITA"]),
                ("Formatta magazzino", "Classifica e prepara il file valore del magazzino.", p["FORMATTA_MAGAZZINO"], p["RAW_FILES"], "VALORE_DEL_MAGAZZINO*.csv"),
            ]),
        ]
        definitions = (
            ("dashboard", DashboardPage(self.show_page, p, self.set_raw_folder)),
            ("operations", WorkflowPage(operations, self.terminal)),
            ("campaigns", WorkflowPage(campaigns, self.terminal, columns=3)),
            ("tools", WorkflowPage(tools, self.terminal)),
        )
        for name, page in definitions:
            self.page_map[name] = page
            self.pages.addWidget(page)

    def show_page(self, name):
        self.pages.setCurrentWidget(self.page_map[name])
        self.sidebar.select(name)
        copy = {
            "dashboard": ("Panoramica", "Centro operativo", "File di input e accesso immediato ai flussi."),
            "operations": ("Esecuzione", "Giornalieri", "Le attività ricorrenti Business e Consumer."),
            "campaigns": ("Workflow", "Campagne", "Dalla divisione dei file fino alla presa in carico."),
            "tools": ("Supporto", "Utilità", "Formattazioni e procedure specialistiche."),
        }
        self.header.set_page(*copy[name])

    def set_raw_folder(self, folder):
        """Aggiorna e persiste la cartella RAW usata da tutte le procedure."""
        folder = Path(folder)
        self.paths["RAW_FILES"] = folder
        salva_cartella_raw(folder, self.sharepoint_root)
        for tile in self.findChildren(ScriptTile):
            if tile.filename:
                tile.folder = folder
                tile.refresh_status()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            QApplication.quit()


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
