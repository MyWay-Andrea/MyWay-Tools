"""Caricamento centralizzato delle variabili definite in SCRIPT/.env."""

from __future__ import annotations

import os
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env"


def carica_env(percorso: Path = ENV_PATH) -> Path:
    """Carica un file .env senza sovrascrivere variabili già presenti."""

    if not percorso.is_file():
        raise FileNotFoundError(f"File di configurazione non trovato: {percorso}")

    with percorso.open("r", encoding="utf-8-sig") as file:
        for numero_riga, riga in enumerate(file, start=1):
            riga = riga.strip()
            if not riga or riga.startswith("#"):
                continue
            if "=" not in riga:
                raise ValueError(
                    f"Riga {numero_riga} non valida in {percorso}: manca '='"
                )
            chiave, valore = riga.split("=", 1)
            chiave = chiave.strip()
            if not chiave:
                raise ValueError(
                    f"Riga {numero_riga} non valida in {percorso}: chiave vuota"
                )
            os.environ.setdefault(chiave, valore.strip())

    return percorso


carica_env()
