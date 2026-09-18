import os
import subprocess
import sys
import tempfile
import threading
import traceback
from pathlib import Path

import requests
from packaging import version
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                               QProgressBar, QPushButton, QVBoxLayout, QWidget)

GITHUB_USER = "MyWay-stage"
GITHUB_REPO = "MyWay-Tools"
RELEASE_API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
SETUP_ASSET_NAME = "setup.exe"


def _get_log_path() -> Path:
    base = Path(os.environ.get("APPDATA", tempfile.gettempdir())) / "MyWayTools"
    base.mkdir(parents=True, exist_ok=True)
    return base / "updater_debug.txt"


def _log(message: str, reset: bool = False) -> None:
    try:
        with _get_log_path().open("w" if reset else "a", encoding="utf-8") as stream:
            stream.write(message.rstrip() + "\n")
    except OSError:
        pass


def get_asset(filename: str) -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for candidate in (exe_dir, exe_dir / "_internal"):
            path = candidate / filename
            if path.exists():
                return path
    return Path(__file__).parent / filename


def get_current_version() -> str:
    try:
        return get_asset("version.txt").read_text(encoding="utf-8").strip().lstrip("vV")
    except (OSError, UnicodeError):
        return "0.0.0"


class _RoundedDialog(QDialog):
    def __init__(self, height: int, parent=None):
        super().__init__(parent)
        self.setFixedSize(460, height)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for i in range(10, 0, -1):
            painter.setBrush(QColor(0, 0, 0, 5 * i))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(i, i, -i, -i), 14, 14)
        path = QPainterPath()
        path.addRoundedRect(10.0, 10.0, self.width() - 20.0,
                            self.height() - 20.0, 12.0, 12.0)
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)


def _base_layout(dialog: QDialog) -> QVBoxLayout:
    dialog.setStyleSheet("QLabel { background:transparent; }")
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(40, 36, 40, 32)
    layout.setSpacing(12)
    bar = QWidget(dialog)
    bar.setGeometry(10, 10, 440, 6)
    bar.setStyleSheet("background:#E60000; border-top-left-radius:12px; border-top-right-radius:12px;")
    row = QHBoxLayout()
    logo = QLabel()
    icon_path = get_asset("logo.ico")
    if icon_path.exists():
        logo.setPixmap(QPixmap(str(icon_path)).scaled(
            38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    else:
        logo.setText("●")
        logo.setStyleSheet("color:#E60000; font-size:28px; font-weight:bold;")
    row.addWidget(logo)
    name = QLabel("MyWay Tools")
    name.setStyleSheet("color:#1A1A1A; font-size:18px; font-weight:bold;")
    row.addWidget(name)
    row.addStretch()
    layout.addLayout(row)
    return layout


class _UpdatePrompt(_RoundedDialog):
    def __init__(self, current: str, latest: str, parent=None):
        super().__init__(260, parent)
        self.setWindowTitle("MyWay Tools — Aggiornamento disponibile")
        layout = _base_layout(self)
        title = QLabel("🎉  Nuova versione disponibile!")
        title.setStyleSheet("color:#1A1A1A; font-size:15px; font-weight:bold;")
        layout.addWidget(title)
        info = QLabel(f"Versione attuale: <b>{current}</b>  →  Nuova versione: <b>{latest}</b>")
        info.setStyleSheet("color:#555555; font-size:13px;")
        layout.addWidget(info)
        description = QLabel("L'aggiornamento verrà scaricato in background.\n"
                             "L'app si chiuderà prima dell'installazione e si riaprirà al termine.")
        description.setWordWrap(True)
        description.setStyleSheet("color:#999999; font-size:12px;")
        layout.addWidget(description)
        buttons = QHBoxLayout()
        later = QPushButton("Più tardi")
        update = QPushButton("🔄  Aggiorna ora")
        later.setStyleSheet("QPushButton { background:#F5F5F5; color:#555; border:1px solid #E0E0E0; border-radius:8px; font-size:14px; font-weight:bold; padding:10px 20px; }")
        update.setStyleSheet("QPushButton { background:#E60000; color:white; border:none; border-radius:8px; font-size:14px; font-weight:bold; padding:10px 20px; }")
        later.clicked.connect(self.reject)
        update.clicked.connect(self.accept)
        buttons.addWidget(later)
        buttons.addWidget(update)
        layout.addLayout(buttons)


class _DownloadDialog(_RoundedDialog):
    def __init__(self, current: str, latest: str, parent=None):
        super().__init__(230, parent)
        self.setWindowTitle("MyWay Tools — Aggiornamento")
        self.setModal(True)
        layout = _base_layout(self)
        info = QLabel(f"Aggiornamento in corso: {current}  →  {latest}")
        info.setStyleSheet("color:#555555; font-size:13px;")
        layout.addWidget(info)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet("QProgressBar { border:none; border-radius:4px; background:#EDEDED; color:transparent; } QProgressBar::chunk { background:#E60000; border-radius:4px; }")
        layout.addWidget(self.progress)
        self.status = QLabel("Scaricamento in corso...")
        self.status.setStyleSheet("color:#999999; font-size:12px;")
        layout.addWidget(self.status)
        self.finished = False

    def closeEvent(self, event):
        event.accept() if self.finished else event.ignore()


class _UpdaterSignals(QObject):
    check_finished = Signal(object, object, object)
    progress = Signal(int)
    download_finished = Signal(object, object)


class UpdateController(QObject):
    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self.signals = _UpdaterSignals()
        self.signals.check_finished.connect(self._on_check_finished)
        self.signals.progress.connect(self._on_progress)
        self.signals.download_finished.connect(self._on_download_finished)
        self.current = get_current_version()
        self.latest = self.setup_url = self.tmp_path = self.download_dialog = None

    def start(self) -> None:
        threading.Thread(target=self._check_release, daemon=True).start()

    def _check_release(self) -> None:
        try:
            response = requests.get(RELEASE_API_URL,
                headers={"Accept": "application/vnd.github+json"}, timeout=(5, 15))
            response.raise_for_status()
            release = response.json()
            latest = str(release["tag_name"]).strip().lstrip("vV")
            setup_url = next(asset["browser_download_url"]
                for asset in release.get("assets", [])
                if asset.get("name", "").lower() == SETUP_ASSET_NAME)
            _log(f"locale: {self.current}\nrelease: {latest}\nasset: {setup_url}", reset=True)
            self.signals.check_finished.emit(latest, setup_url, None)
        except Exception as exc:
            _log(f"Errore controllo release: {exc}\n{traceback.format_exc()}", reset=True)
            self.signals.check_finished.emit(None, None, str(exc))

    def _on_check_finished(self, latest, setup_url, error) -> None:
        if error:
            return
        try:
            if version.parse(latest) <= version.parse(self.current):
                return
        except version.InvalidVersion as exc:
            _log(f"Versione non valida: {exc}")
            return
        self.latest, self.setup_url = latest, setup_url
        parent = self.app.activeWindow()
        if _UpdatePrompt(self.current, latest, parent).exec() == QDialog.Accepted:
            self._start_download(parent)

    def _start_download(self, parent) -> None:
        self.download_dialog = _DownloadDialog(self.current, self.latest, parent)
        self.download_dialog.show()
        self.tmp_path = Path(tempfile.gettempdir()) / f"myway_update_{os.getpid()}.exe"
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self) -> None:
        try:
            with requests.get(self.setup_url, timeout=(10, 120), stream=True,
                              allow_redirects=True) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))
                downloaded, last_percent = 0, -1
                with self.tmp_path.open("wb") as stream:
                    for chunk in response.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        stream.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            percent = min(99, int(downloaded * 100 / total))
                            if percent != last_percent:
                                last_percent = percent
                                self.signals.progress.emit(percent)
            size = self.tmp_path.stat().st_size
            with self.tmp_path.open("rb") as stream:
                signature = stream.read(2)
            if size < 500_000 or signature != b"MZ":
                raise ValueError(f"File non valido ({size / 1024:.0f} KB).")
            _log(f"Download completato: {self.tmp_path} ({size / 1024 / 1024:.2f} MB)")
            self.signals.download_finished.emit(str(self.tmp_path), None)
        except Exception as exc:
            _log(f"Errore download: {exc}\n{traceback.format_exc()}")
            try:
                self.tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            self.signals.download_finished.emit(None, str(exc))

    def _on_progress(self, percent: int) -> None:
        if self.download_dialog:
            self.download_dialog.progress.setValue(percent)
            self.download_dialog.status.setText(f"Scaricamento... {percent}%")

    def _on_download_finished(self, installer, error) -> None:
        if not self.download_dialog:
            return
        if error:
            self.download_dialog.finished = True
            self.download_dialog.progress.setValue(0)
            self.download_dialog.status.setText(f"❌  {error}")
            QTimer.singleShot(5000, self.download_dialog.close)
            return
        self.download_dialog.progress.setValue(100)
        self.download_dialog.status.setText("✅  Chiusura dell'app e installazione...")
        try:
            self._launch_install_helper(Path(installer))
        except Exception as exc:
            _log(f"Errore avvio helper: {exc}\n{traceback.format_exc()}")
            self.download_dialog.finished = True
            self.download_dialog.status.setText(f"❌  Impossibile avviare l'installer: {exc}")
            QTimer.singleShot(5000, self.download_dialog.close)
            return
        QTimer.singleShot(200, self.app.quit)

    def _launch_install_helper(self, installer: Path) -> None:
        frozen = getattr(sys, "frozen", False)
        restart_target = Path(sys.executable) if frozen else Path(__file__).with_name("menu.py")
        restart_line = (f'start "" "{restart_target}"' if frozen else
                        f'start "" "{sys.executable}" "{restart_target}"')
        helper = Path(tempfile.gettempdir()) / f"myway_update_{os.getpid()}.cmd"
        helper.write_text(
            "@echo off\n"
            f'powershell.exe -NoProfile -WindowStyle Hidden -Command "Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue"\n'
            f'start /wait "" "{installer}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART\n'
            "if errorlevel 1 exit /b %errorlevel%\n"
            f"{restart_line}\n"
            f'del /q "{installer}"\n'
            'del /q "%~f0"\n', encoding="utf-8")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        subprocess.Popen(["cmd.exe", "/d", "/c", str(helper)],
                         creationflags=flags, close_fds=True)
        _log(f"Helper avviato: {helper}")


def check_and_update(app: QApplication) -> UpdateController:
    """Avvia il controllo senza bloccare il thread grafico."""
    controller = getattr(app, "_myway_update_controller", None)
    if controller is None:
        controller = UpdateController(app)
        app._myway_update_controller = controller
        controller.start()
    return controller
