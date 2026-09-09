# ─────────────────────────────────────────────────────────────
# REQUISITO: pip install PySide6
# ─────────────────────────────────────────────────────────────
import sys
import os
import re
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from updater import get_asset

from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QScrollArea, QTextEdit,
    QSizePolicy, QStackedWidget, QGridLayout, QSpacerItem,
    QFileDialog, QMessageBox, QSplashScreen, QDialog,
    QDialogButtonBox, QLineEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QSize
from PySide6.QtGui import (
    QColor, QTextCharFormat, QTextCursor,
    QIcon, QPixmap, QPainter, QFont, QLinearGradient, QBrush
)


# ── DEBUG TEMPORANEO ──────────────────────────────────────
def debug_info():
    exe_dir  = Path(sys.executable).parent
    internal = exe_dir / '_internal'
    
    lines = [
        f"frozen: {getattr(sys, 'frozen', False)}",
        f"sys.executable: {sys.executable}",
        f"exe_dir: {exe_dir}",
        f"_internal exists: {internal.exists()}",
        f"version.txt in exe_dir: {(exe_dir / 'version.txt').exists()}",
        f"version.txt in _internal: {(internal / 'version.txt').exists()}",
        f"logo.ico in _internal: {(internal / 'logo.ico').exists()}",
    ]
    
    if (internal / 'version.txt').exists():
        lines.append(f"version letta: {(internal / 'version.txt').read_text().strip()}")
    
    msg = "\n".join(lines)
    
    # Scrive su file così lo vedi anche senza console
    debug_path = Path(os.environ["APPDATA"]) / "MyWayTools" / "debug.txt"
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(msg)

debug_info()
# ── FINE DEBUG ────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# APP DIR  (funziona sia da .py che da .exe PyInstaller)
# ─────────────────────────────────────────────────────────────
def get_app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

BASE_DIR  = get_app_dir()
ICON_PATH = get_asset("logo.ico")

# ─────────────────────────────────────────────────────────────
# CONFIG  ─  lettura / scrittura config.json
# ─────────────────────────────────────────────────────────────
CONFIG_PATH = get_asset("config.json")

# Struttura relativa attesa dentro la cartella SharePoint.
# Le chiavi corrispondono alle variabili PATH_* del vecchio codice.
_REL_PATHS = {
    "RAW_FILES"                 :"SCRIPT/00_RAW_FILE",
    # BUSINESS
    "ESTRAI_FILE_GARA"             : "SCRIPT/BUSINESS/13_ESTRAI_FILE_GARA/ESTRAI_FILE_GARA.py",
    "FCST"                      : "SCRIPT/BUSINESS/12_FCST_BUSINESS/crea_report_aggregato.py",
    "APPUNTAMENTI_SETTIMANA"    : "SCRIPT/BUSINESS/02_APPUNTAMENTI_SETTIMANA/script/ESTRAI_APPUNTMANETI_SETTIMANA.py",
        #altri script
    "FORMATTA_GARA"             : "SCRIPT/BUSINESS/09_ESTRAZIONE_ORDINI_API/AGGREGA_STORICO.py",
    "FORMATTA_OPPORTUNITA"      : "SCRIPT/BUSINESS/10_ESTRAZIONE_OPP_API/AGGREGA_STORICO.py",
    "FORMATTA_APPUNTAMENTI"     : "SCRIPT/BUSINESS/11_ESTRAZIONE_APP_API/AGGREGA_STORICO.py",
    "CHIUSURA_GARA"             : "SCRIPT/BUSINESS/09_ESTRAZIONE_ORDINI_API/CHIUSURA_GARA.py",
        #campagne
    "DIVIDI_FILE_CAMPAGNE"      : "SCRIPT/BUSINESS/CAMPAGNE/00_DIVIDI_FILE_CAMPAGNE/DIVIDI_CAMPAGNE.py",
    "AGGREGA_FILE_VENDITORI"    : "SCRIPT/BUSINESS/CAMPAGNE/01_AGGREGA_FILE_VENDITORI/AGGREGA_FILE.py",
    "PRESA_IN_CARICO"           : "SCRIPT/BUSINESS/CAMPAGNE/02_CONTROLLA_PRESA_IN_CARICO/PRESA_IN_CARICO.py",
    "REPORT_CAMPAGNE"           : "",
    # CONSUMER
    
    "REPORT_PEDONALITA"         : "SCRIPT/CONSUMER/02_REPORT_PEDONALITA/script/CREA_REPORT_PEDONALITA.py",
    "CRUSCOTTO_TRACCIAMENTO"     : "SCRIPT/CONSUMER/11_CRUSCOTTO_AGGREGATIVO/CRUSCOTTO_AGGREGATIVO.py",
    "CRUSCOTTO_GIORNALIERO"     : "SCRIPT/CONSUMER/12_CRUSCOTTO_PISTA_CONSUMER/main.py",
    
        #altri script
    "FORMATTA_PEDONALITA"       : "SCRIPT/CONSUMER/01_FORMATTA_PEDONALITA/script/FORMATTA_PEDONALITA.py",
    "FORMATTA_MAGAZZINO"        : "SCRIPT/CONSUMER/03_FORMATTA_MAGAZZINO/FORMATTA_MAGAZZINO.py",

}

def _build_paths(sharepoint_root: Path) -> dict:
    """Costruisce il dizionario dei path assoluti a partire dalla root SharePoint."""
    return {key: sharepoint_root / rel for key, rel in _REL_PATHS.items()}

def carica_config() -> dict | None:
    """Legge config.json. Restituisce None se non esiste o è corrotto."""
    if not CONFIG_PATH.exists():
        return None
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        root = Path(data.get("sharepoint_root", ""))
        if not root.exists():
            return None          # cartella non più raggiungibile
        return data
    except Exception:
        return None

def salva_config(sharepoint_root: Path) -> None:
    """Salva config.json con la root SharePoint scelta dall'utente."""
    data = {"sharepoint_root": str(sharepoint_root)}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────
# DIALOG DI PRIMA CONFIGURAZIONE
# ─────────────────────────────────────────────────────────────
class ConfigDialog(QDialog):
    """
    Mostrata all'avvio se config.json manca o la cartella non esiste.
    Chiede all'utente di scegliere la cartella SharePoint sincronizzata
    in locale (quella che contiene la sottocartella SCRIPT/).
    """
    def __init__(self, messaggio_extra: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurazione – MyWay Tools")
        self.setFixedWidth(540)
        self.setStyleSheet(f"background:{C_BG};")
        self.sharepoint_root: Path | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 30, 30, 24)
        lay.setSpacing(14)

        # Icona + titolo
        titolo = QLabel("📁  Imposta cartella SharePoint")
        titolo.setStyleSheet(f"font-size:18px; font-weight:bold; color:{C_TEXT_DARK};")
        lay.addWidget(titolo)

        if messaggio_extra:
            lbl_warn = QLabel(f"⚠️  {messaggio_extra}")
            lbl_warn.setStyleSheet(f"font-size:13px; color:{C_LOG_WARN}; background:#FFF8E7; "
                                    f"border:1px solid #FBBF24; border-radius:8px; padding:8px 12px;")
            lbl_warn.setWordWrap(True)
            lay.addWidget(lbl_warn)

        desc = QLabel(
            "Seleziona la cartella SharePoint sincronizzata in locale.\n"
            "Deve contenere la sottocartella  <b>SCRIPT/</b>  con tutti gli script.\n\n"
            "Esempio:  <code>C:/Users/mario/MyWay</code>"
        )
        desc.setStyleSheet(f"font-size:13px; color:{C_TEXT_MID};")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Campo path + pulsante sfoglia
        row = QHBoxLayout()
        self.field = QLineEdit()
        self.field.setPlaceholderText("Percorso cartella SharePoint…")
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
        hint = QLabel(f"💡 La tua home è:  <code>{Path.home()}</code>")
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
            self, "Seleziona cartella SharePoint", str(Path.home())
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
                                "Assicurati che SharePoint sia sincronizzato.")
            return
        self.sharepoint_root = path
        salva_config(path)
        self.accept()


# ─────────────────────────────────────────────────────────────
# PALETTE COLORI
# ─────────────────────────────────────────────────────────────
C_BG         = "#F5F0EB"
C_PANEL      = "#FFFFFF"
C_SIDEBAR    = "#FFFFFF"
C_RED        = "#E60000"
C_RED_HOVER  = "#CC0000"
C_RED_LIGHT  = "#FFF0F0"
C_TEXT_DARK  = "#1A1A1A"
C_TEXT_MID   = "#555555"
C_TEXT_LIGHT = "#999999"
C_BORDER     = "#E8E2DC"

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


# ─────────────────────────────────────────────────────────────
# TERMINALE WIDGET
# ─────────────────────────────────────────────────────────────
class TerminaleWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(210)
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

    if not script_path.exists():
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
        env["BASE_DIR"] = str(BASE_DIR)

        try:
            process = subprocess.Popen(
                [python_exe, "-u", str(script_path)],
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
CARD_HEIGHT        = 320
CARD_HEIGHT_STATUS = 320

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

        self.setStyleSheet(f"""
            ScriptCard {{ background:{C_PANEL}; border-radius:14px; border:1px solid {C_BORDER}; }}
            ScriptCard:hover {{ background:#FFF8F8; border:1px solid {C_RED}; }}
        """)
        self.setFixedHeight(CARD_HEIGHT_STATUS if cartella else CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(180)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(6)

        top = QHBoxLayout()
        lbl_icona = QLabel(icona)
        lbl_icona.setStyleSheet(f"font-size:36px; color:{C_RED}; background:transparent; border:none;")
        top.addWidget(lbl_icona)
        num = titolo.split(".")[0].strip()
        lbl_num = QLabel(f"  {num:>02}")
        lbl_num.setStyleSheet(f"background:{C_RED_LIGHT}; color:{C_RED}; border-radius:7px; font-size:18px; font-weight:bold; padding:4px 10px; border:none;")
        lbl_num.setFixedHeight(34)
        top.addWidget(lbl_num)
        top.addStretch()
        lay.addLayout(top)

        titolo_pulito = titolo.split(".", 1)[-1].strip()
        lbl_titolo = QLabel(titolo_pulito)
        lbl_titolo.setStyleSheet(f"font-size:16px; font-weight:bold; color:{C_TEXT_DARK}; background:transparent; border:none;")
        lbl_titolo.setWordWrap(True)
        lay.addWidget(lbl_titolo)

        lbl_desc = QLabel(descrizione)
        lbl_desc.setStyleSheet(f"font-size:13px; color:{C_TEXT_LIGHT}; background:transparent; border:none;")
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
            placeholder.setFixedHeight(40)
            placeholder.setStyleSheet("background:transparent; border:none;")
            lay.addWidget(placeholder)

        self.btn_avvia = QPushButton("Avvia  →")
        self.btn_avvia.setStyleSheet(f"""
            QPushButton {{ background:{C_RED}; color:white; border:none; border-radius:7px; font-size:15px; font-weight:bold; padding:8px 18px; }}
            QPushButton:hover {{ background:{C_RED_HOVER}; }}
            QPushButton:disabled {{ background:#CCCCCC; color:#888888; }}
        """)
        self.btn_avvia.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_avvia.setFixedWidth(180)
        self.btn_avvia.setFixedHeight(40)
        self.btn_avvia.clicked.connect(self._on_avvia_clicked)
        lay.addWidget(self.btn_avvia, alignment=Qt.AlignLeft)

        if self.cartella:
            self.timer_stato = QTimer(self)
            self.timer_stato.timeout.connect(self._aggiorna_stato)
            self.timer_stato.start(1000)
            self._aggiorna_stato()

        self._signals = ScriptCardSignals()
        self._signals.script_finished.connect(self._on_script_finished)
        global_signals.script_avviato.connect(self._on_qualsiasi_script_avviato)
        global_signals.script_terminato.connect(self._on_qualsiasi_script_terminato)

    def _on_avvia_clicked(self):
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

    def __init__(self, cartella: Path, parent=None):
        super().__init__(parent)
        self.cartella = Path(cartella)
        self.setStyleSheet(f"RawFilesWidget {{ background:{C_PANEL}; border-radius:14px; border:1px solid {C_BORDER}; }}")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(10)

        header_row = QHBoxLayout()
        icona = QLabel("📁")
        icona.setStyleSheet(f"font-size:22px; color:{C_RED}; background:transparent; border:none;")
        header_row.addWidget(icona)
        lbl_titolo = QLabel("Raw Files")
        lbl_titolo.setStyleSheet(f"font-size:15px; font-weight:bold; color:{C_TEXT_DARK}; background:transparent; border:none;")
        header_row.addWidget(lbl_titolo)
        header_row.addStretch()
        self.lbl_count = QLabel("0 file")
        self.lbl_count.setStyleSheet(f"background:{C_RED}; color:white; border-radius:10px; font-size:12px; font-weight:bold; padding:2px 10px; border:none;")
        header_row.addWidget(self.lbl_count)
        btn_carica = QPushButton("+ Carica file")
        btn_carica.setStyleSheet(f"""
            QPushButton {{ background:{C_RED}; color:white; border:none; border-radius:7px; font-size:13px; font-weight:bold; padding:6px 14px; }}
            QPushButton:hover {{ background:{C_RED_HOVER}; }}
        """)
        btn_carica.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_carica.clicked.connect(self._carica_file)
        header_row.addWidget(btn_carica)
        outer.addLayout(header_row)

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
        self._timer.start(1000)
        self._aggiorna_lista()

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

    def _aggiorna_lista(self):
        files = self._leggi_files()
        self.lbl_count.setText(f"{len(files)} file" if len(files) != 1 else "1 file")
        nomi_attuali = {
            self.lista_layout.itemAt(i).widget().property("nome_file")
            for i in range(self.lista_layout.count())
            if self.lista_layout.itemAt(i).widget()
        }
        if nomi_attuali == {f.name for f in files}: return
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
    lay.setContentsMargins(8, 18, 8, 10)
    lay.setSpacing(0)
    bar = QFrame()
    bar.setFixedSize(4, 20)
    bar.setStyleSheet(f"background:{C_RED}; border:none; border-radius:2px;")
    lay.addWidget(bar)
    lay.addSpacing(10)
    lbl = QLabel(testo)
    lbl.setStyleSheet(f"color:{C_TEXT_MID}; font-size:15px; font-weight:bold; background:transparent; border:none;")
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
        bg     = C_RED_LIGHT if attivo else "transparent"
        border = f"border:2px solid {C_RED}; border-radius:10px;" if attivo else "border:none; border-radius:10px;"
        self.setStyleSheet(f"QFrame {{ background:{bg}; {border} }}")
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        header = QFrame()
        header.setStyleSheet("background:transparent; border:none;")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(8, 6, 8, 6)
        h_lay.setSpacing(0)
        if attivo:
            linea = QFrame()
            linea.setFixedSize(4, 20)
            linea.setStyleSheet(f"background:{C_RED}; border:none;")
            h_lay.addWidget(linea)
        fg   = C_RED if attivo else C_TEXT_MID
        peso = "bold" if attivo else "normal"
        lbl  = QLabel(f"  {icona}  {testo}")
        lbl.setStyleSheet(f"color:{fg}; font-size:17px; font-weight:{peso}; background:transparent; border:none;")
        lbl.setCursor(Qt.PointingHandCursor)
        h_lay.addWidget(lbl)
        h_lay.addStretch()
        lay.addWidget(header)
        if attivo and sottovoci:
            content = QFrame()
            content.setStyleSheet("background:transparent; border:none;")
            c_lay = QVBoxLayout(content)
            c_lay.setContentsMargins(12, 0, 12, 6)
            c_lay.setSpacing(2)
            linea_sep = QFrame()
            linea_sep.setFixedHeight(1)
            linea_sep.setStyleSheet(f"background:{C_RED}; border:none;")
            c_lay.addWidget(linea_sep)
            for sezione, voci in sottovoci:
                s_frame = QFrame()
                s_frame.setStyleSheet("background:transparent; border:none;")
                s_lay = QHBoxLayout(s_frame)
                s_lay.setContentsMargins(2, 4, 0, 2)
                s_lay.setSpacing(6)
                bar = QFrame()
                bar.setFixedSize(3, 14)
                bar.setStyleSheet(f"background:{C_RED}; border:none;")
                s_lay.addWidget(bar)
                lbl_s = QLabel(sezione)
                lbl_s.setStyleSheet(f"color:{C_RED}; font-size:15px; font-weight:bold; background:transparent; border:none;")
                s_lay.addWidget(lbl_s)
                s_lay.addStretch()
                c_lay.addWidget(s_frame)
                for voce in voci:
                    v_lbl = QLabel(f"· {voce}")
                    v_lbl.setStyleSheet(f"color:{C_TEXT_MID}; font-size:14px; padding-left:20px; background:transparent; border:none;")
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
        self.setFixedWidth(300)
        self.setStyleSheet(f"QFrame {{ background:{C_SIDEBAR}; border:none; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        barra = QFrame()
        barra.setFixedHeight(5)
        barra.setStyleSheet(f"background:{C_RED}; border:none;")
        lay.addWidget(barra)

        logo_frame = QFrame()
        logo_frame.setStyleSheet("background:transparent; border:none;")
        logo_lay = QHBoxLayout(logo_frame)
        logo_lay.setContentsMargins(30, 35, 30, 10)
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
        lbl_title.setStyleSheet(f"color:{C_TEXT_DARK}; font-size:22px; font-weight:bold; background:transparent;")
        logo_lay.addWidget(lbl_title)
        logo_lay.addStretch()
        lay.addWidget(logo_frame)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C_BORDER}; border:none; margin-left:20px; margin-right:20px;")
        lay.addWidget(sep)
        lay.addSpacing(10)

        lbl_nav = QLabel("NAVIGAZIONE")
        lbl_nav.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:11px; background:transparent; border:none;")
        lbl_nav.setContentsMargins(28, 0, 0, 8)
        lay.addWidget(lbl_nav)

        home_sottovoci        = [] if pagina_attiva == "main" else None
        giornalieri_sottovoci = [
            ("Business",          ["Estrai file gara", "FCST", "Appuntamenti"]),
            ("Consumer / Negozi", ["Report pedonalità", "Cruscotto Tracciamento", "Cruscotto Giornaliero"]),
        ] if pagina_attiva == "giornalieri" else None
        campagne_sottovoci    = [
            ("Campagne", ["Divisione per aente", "Riaggrega file Campagne", "Presa in carico cliente", "Report Campagne(⚒️)"]),
        ] if pagina_attiva == "campagne" else None
        altro_sottovoci       = [
            ("Business", ["Formatta file Gara", "Formatta file appuntamenti", "Formatta file opportunità", "Chiusura gara"]),
            ("Formattazione file negozi", ["Formatta pedonalità", "Formatta magazzino", "Formatta performance(⚒️)"])
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
            f_lay.setContentsMargins(16, 2, 16, 2)
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
        sep2.setStyleSheet(f"background:{C_BORDER};")
        b_lay.addWidget(sep2)

        # Path SharePoint corrente
        lbl_sp = QLabel("📂  SharePoint:")
        lbl_sp.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:11px; background:transparent; border:none;")
        b_lay.addWidget(lbl_sp)

        lbl_sp_path = QLabel(str(sharepoint_root))
        lbl_sp_path.setStyleSheet(f"color:{C_TEXT_MID}; font-size:11px; background:transparent; border:none;")
        lbl_sp_path.setWordWrap(True)
        b_lay.addWidget(lbl_sp_path)

        btn_cambia = QPushButton("🔧  Cambia cartella SharePoint")
        btn_cambia.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{C_RED}; border:1px solid {C_RED};
                border-radius:8px; font-size:13px; padding:6px; text-align:left; }}
            QPushButton:hover {{ background:#FFEBEB; }}
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
        sep3.setStyleSheet(f"background:{C_BORDER};")
        b_lay.addWidget(sep3)

        btn_esci = QPushButton("Esci")
        btn_esci.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{C_RED}; border:none; border-radius:8px;
                font-size:20px; padding:8px; text-align:left; }}
            QPushButton:hover {{ background:#FFEBEB; }}
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
        self.setFixedHeight(100)
        self.setStyleSheet(f"background:{C_BG}; border:none;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(25, 5, 25, 5)
        left = QFrame()
        left.setStyleSheet("background:transparent; border:none;")
        l_lay = QVBoxLayout(left)
        l_lay.setContentsMargins(0, 0, 0, 0)
        l_lay.setSpacing(1)
        self.lbl_breadcrumb  = QLabel("Home")
        self.lbl_breadcrumb.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:14px;")
        self.lbl_titolo      = QLabel("MyWay Tools")
        self.lbl_titolo.setStyleSheet(f"color:{C_TEXT_DARK}; font-size:30px; font-weight:bold;")
        self.lbl_sottotitolo = QLabel("")
        self.lbl_sottotitolo.setStyleSheet(f"color:{C_TEXT_MID}; font-size:16px;")
        l_lay.addWidget(self.lbl_breadcrumb)
        l_lay.addWidget(self.lbl_titolo)
        l_lay.addWidget(self.lbl_sottotitolo)
        lay.addWidget(left)
        lay.addStretch()
        self.lbl_orologio = QLabel("")
        self.lbl_orologio.setStyleSheet("color:#000000; font-size:18px;")
        lay.addWidget(self.lbl_orologio, alignment=Qt.AlignRight | Qt.AlignVCenter)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._aggiorna_orologio)
        self._timer.start(1000)
        self._aggiorna_orologio()

    def _aggiorna_orologio(self):
        self.lbl_orologio.setText(datetime.now().strftime("📅 %d %b %Y   🕒 %H:%M:%S"))

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
        lay.setContentsMargins(50, 50, 50, 30)
        lay.setSpacing(0)
        lbl_welcome = QLabel("Bentornato 👋")
        lbl_welcome.setStyleSheet(f"color:{C_TEXT_LIGHT}; font-size:14px;")
        lay.addWidget(lbl_welcome)
        linea_red = QFrame()
        linea_red.setFixedSize(60, 3)
        linea_red.setStyleSheet(f"background:{C_RED}; border-radius:2px;")
        lay.addWidget(linea_red)
        lay.addSpacing(30)
        cards_frame = QFrame()
        cards_frame.setStyleSheet("background:transparent; border:none;")
        c_lay = QHBoxLayout(cards_frame)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(28)
        c_lay.addWidget(self._big_card("◈", "Giornalieri",
            "Seszione in cui puoi trovare tutti gli script utili per le operazioni quitidiane.\nPuoi trovare sia script inerenti a lato BUSINESS sia a lato CONSUMER",
            "Operatività quotidiana", "giornalieri", nav_callback))
        c_lay.addWidget(self._big_card("◉", "Campagne",
            "Divisione campagne per agente, avanzamento, report e statistiche complete.",
            "Gestione campagne", "campagne", nav_callback))
        lay.addWidget(cards_frame)
        lay.addSpacing(28)
        lay.addWidget(crea_section_label("Raw Files · Cartella di input"))
        lay.addSpacing(6)
        self.raw_files_widget = RawFilesWidget(paths["RAW_FILES"])
        lay.addWidget(self.raw_files_widget)
        lay.addStretch()
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll)

    def _big_card(self, icona, titolo, desc, tag, pagina, nav_callback):
        card = QFrame()
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setMinimumHeight(280)
        card.setStyleSheet(f"QFrame {{ background:{C_PANEL}; border-radius:20px; border:1px solid {C_BORDER}; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(0)
        lbl_tag = QLabel(f"  {tag}  ")
        lbl_tag.setStyleSheet(f"background:{C_RED_LIGHT}; color:{C_RED}; border-radius:6px; font-size:11px; font-weight:bold; padding:2px 8px; border:none;")
        lbl_tag.setFixedHeight(24)
        lbl_tag.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lay.addWidget(lbl_tag)
        lay.addSpacing(14)
        lbl_icona = QLabel(icona)
        lbl_icona.setStyleSheet(f"font-size:44px; color:{C_RED}; background:transparent; border:none;")
        lay.addWidget(lbl_icona)
        lay.addSpacing(4)
        lbl_titolo = QLabel(titolo)
        lbl_titolo.setStyleSheet(f"font-size:22px; font-weight:bold; color:{C_TEXT_DARK}; background:transparent; border:none;")
        lay.addWidget(lbl_titolo)
        lay.addSpacing(6)
        lbl_desc = QLabel(desc)
        lbl_desc.setStyleSheet(f"font-size:13px; color:{C_TEXT_MID}; background:transparent; border:none;")
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
        grid.setContentsMargins(38, 20, 38, 20)
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
            {"icona": "📊", "titolo": "1. Report Pedonalità",
             "desc": "Creazione report per analisi flussi di pedonalità nei punti vendita.",
             "script": paths["REPORT_PEDONALITA"]},
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
                              cartella=cfg.get("cartella"), nomi_file=cfg.get("nomi_file"))
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
        grid.setContentsMargins(38, 20, 38, 20)
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
        grid.setContentsMargins(38, 20, 38, 20)
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
        grid.addWidget(crea_section_label("Formattazione file negozi"), row, 0, 1, 12); row += 1
        cards_consumer = [
            ("🗂️", "1. Formatta pedonalità",  "Formatta e prepara file pedonalità",            paths["FORMATTA_PEDONALITA"], paths["RAW_FILES"], "Giorgio Mandelli*.xlsx"),
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
        self.sidebar_stack.setFixedWidth(300)
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
        r_lay.addWidget(self.content_stack, stretch=1)

        self.terminale = TerminaleWidget()
        r_lay.addWidget(self.terminale)
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
# AVVIO
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(carica_icona())
    app.setStyleSheet("""
        QScrollBar:vertical { background: gray; width: 10px; }
        QScrollBar::handle:vertical { background: gray; }
    """)

    # ── Carica config PRIMA dello splash ──────────────────────
    config = carica_config()

    if config is None:
        messaggio = (
            "Cartella SharePoint non raggiungibile o configurazione mancante."
            if CONFIG_PATH.exists()
            else ""
        )
        dlg = ConfigDialog(messaggio)
        if dlg.exec() != QDialog.Accepted or dlg.sharepoint_root is None:
            sys.exit(0)
        sharepoint_root = dlg.sharepoint_root
    else:
        sharepoint_root = Path(config["sharepoint_root"])

    # ── Solo dopo la config, mostra lo splash ─────────────────
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    # ── Finestra principale ───────────────────────────────────
    window = MainWindow(sharepoint_root)
    QTimer.singleShot(1800, lambda: (splash.finish(window), window.show()))

    # ── Check aggiornamento DOPO che l'app è visibile ─────────
    QTimer.singleShot(2500, lambda: (
        __import__('updater').check_and_update(app)
    ))

    sys.exit(app.exec())
    