"""Versioned, atomic user preferences, independent from operational config.json."""
import json
import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QObject, Signal


DEFAULT_FAVORITES = [
    "estrai_file_gara", "forecast_business", "formatta_pedonalita",
    "cruscotto_tracciamento", "cruscotto_giornaliero",
]


def profile_dir():
    return Path(os.environ.get("APPDATA", Path.home())) / "MyWayTools"


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name, suffix=".tmp", delete=False) as file:
            name = file.name
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


class Favorites(QObject):
    changed = Signal()

    def __init__(self, valid_ids, path=None, parent=None):
        super().__init__(parent)
        self.path = Path(path) if path else profile_dir() / "preferences.json"
        self.valid_ids = set(valid_ids)
        self.warning = ""
        defaults = {"schema_version": 1, "favorites": DEFAULT_FAVORITES}
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.data, dict) or self.data.get("schema_version") != 1:
                raise ValueError("Versione preferenze non supportata")
            if not isinstance(self.data.get("favorites"), list) or not all(
                    isinstance(value, str) for value in self.data["favorites"]):
                raise ValueError("Elenco preferiti non valido")
        except FileNotFoundError:
            self.data = defaults
            self._save()
        except (ValueError, OSError):
            # Preserve the original for inspection; never silently overwrite it.
            self.data = defaults
            try:
                if self.path.exists():
                    from uuid import uuid4
                    self.path.replace(self.path.with_suffix(f".invalid-{uuid4().hex}.json"))
                self._save()
                self.warning = "Preferenze non leggibili: originale conservato, ripristinati i preferiti iniziali."
            except OSError:
                self.warning = "Preferenze non accessibili: modifiche disponibili solo in questa sessione."

    @property
    def ids(self):
        # Keep unknown IDs on disk: a temporarily absent activity may return later.
        return list(dict.fromkeys(x for x in self.data["favorites"] if x in self.valid_ids))

    def _save(self):
        atomic_json(self.path, self.data)

    def toggle(self, activity_id):
        if activity_id not in self.valid_ids:
            return
        previous = list(self.data["favorites"])
        self.data["favorites"] = ([x for x in previous if x != activity_id]
                                  if activity_id in previous else previous + [activity_id])
        try:
            self._save()
        except OSError:
            self.data["favorites"] = previous
            raise
        self.changed.emit()
