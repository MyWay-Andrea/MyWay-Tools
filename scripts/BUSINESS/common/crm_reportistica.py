"""Configurazione condivisa per le estrazioni CRM in sola lettura."""

import os
import sys
from pathlib import Path


BUSINESS_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = BUSINESS_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import config_env  # noqa: E402,F401

ENV_PATH = config_env.ENV_PATH
DEFAULT_BASE_URL = "https://app.crmincloud.it/api/v1"

API_KEY = os.getenv("CRM_REPORTISTICA_API_KEY_FCST", "").strip()
BASE_URL = os.getenv("CRM_REPORTISTICA_BASE_URL", DEFAULT_BASE_URL).strip()

if not API_KEY:
    raise RuntimeError(
        "Chiave API reportistica mancante: configura CRM_REPORTISTICA_API_KEY_FCST "
        f"nel file {ENV_PATH}."
    )
