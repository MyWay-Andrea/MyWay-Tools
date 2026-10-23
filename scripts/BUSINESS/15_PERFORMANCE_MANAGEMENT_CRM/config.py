from __future__ import annotations

import json
import os
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
BUSINESS_DIR = PROJECT_DIR.parent
SCRIPT_DIR = BUSINESS_DIR.parent
OUTPUT_DIR = PROJECT_DIR / "output"
LOGO_PATH = PROJECT_DIR / "logo MWR.jpg"
VENDITORI_PATH = BUSINESS_DIR / "config" / "venditori.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BUSINESS_DIR) not in sys.path:
    sys.path.insert(0, str(BUSINESS_DIR))

from common.crm_reportistica import API_KEY, BASE_URL  # noqa: E402


TIMEZONE = "Europe/Rome"
ADMIN_EMAIL = "a.grisoli@mywaysrl.it"
CRM_EMAILS = ["c.febbo@mywaysrl.it", "l.mattaini@mywaysrl.it"]
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID", "").strip()
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID", "").strip()
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET", "").strip()
GRAPH_SENDER_EMAIL = os.getenv("GRAPH_SENDER_EMAIL", "").strip()


def carica_venditori() -> list[dict]:
    with VENDITORI_PATH.open("r", encoding="utf-8") as file:
        dati = json.load(file)
    venditori = dati.get("venditori")
    if not isinstance(venditori, list):
        raise ValueError("La chiave 'venditori' deve contenere una lista")
    return venditori

