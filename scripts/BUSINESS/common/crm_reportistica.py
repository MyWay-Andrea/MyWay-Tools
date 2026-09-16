"""Configurazione condivisa per le estrazioni CRM in sola lettura."""

import os
from pathlib import Path


BUSINESS_DIR = Path(__file__).resolve().parents[1]
SHAREPOINT_ROOT = Path(
    os.getenv(
        "MYWAY_SHAREPOINT_ROOT",
        Path.home() / "My Way S.r.l" / "MyWay Tools - MyWay Tools",
    )
)
ENV_PATH = SHAREPOINT_ROOT / "SCRIPT" / "BUSINESS" / ".env"
DEFAULT_BASE_URL = "https://app.crmincloud.it/api/v1"


def _carica_env() -> None:
    """Carica il file condiviso senza sovrascrivere variabili di sistema."""
    if not ENV_PATH.is_file():
        return

    for riga in ENV_PATH.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue

        chiave, valore = riga.split("=", 1)
        os.environ.setdefault(chiave.strip(), valore.strip())


_carica_env()

API_KEY = os.getenv("CRM_REPORTISTICA_API_KEY_FCST", "").strip()
BASE_URL = os.getenv("CRM_REPORTISTICA_BASE_URL", DEFAULT_BASE_URL).strip()

if not API_KEY:
    raise RuntimeError(
        "Chiave API reportistica mancante: configura CRM_REPORTISTICA_API_KEY_FCST "
        f"nel file {ENV_PATH}."
    )
