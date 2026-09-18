import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

import config_env  # noqa: E402,F401


PATH_PROGETTO = Path(__file__).resolve().parents[2]
PATH_RAW_FILE = PATH_PROGETTO / "00_RAW_FILE"

NOME_FILE_OUTPUT = "TRACCIAMENTO_CONSUMER_{inizio}_{fine}.xlsx"
NOME_FOGLIO_OUTPUT = "CRUSCOTTO CONSUMER"
NOMI_MESI = {
    1: "GENNAIO",
    2: "FEBBRAIO",
    3: "MARZO",
    4: "APRILE",
    5: "MAGGIO",
    6: "GIUGNO",
    7: "LUGLIO",
    8: "AGOSTO",
    9: "SETTEMBRE",
    10: "OTTOBRE",
    11: "NOVEMBRE",
    12: "DICEMBRE",
}

PAROLE_CHIAVE_PISTE = {
    "MOBILE": ("mobile",),
    "WIRELINE": ("wireline",),
    "UPSELLING": ("upselling",),
    "ENERGY": ("energy",),
    "COMMISSIONALI": ("commissionali",),
}

PISTE_ATTESE = tuple(PAROLE_CHIAVE_PISTE)
TIPI_DATO_ATTESI = ("PEZZI", "PUNTI")

# Microsoft Graph. Le credenziali devono essere impostate come variabili d'ambiente.
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID", "").strip()
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID", "").strip()
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET", "").strip()
GRAPH_SENDER_EMAIL = os.getenv("GRAPH_SENDER_EMAIL", "").strip()
EMAIL_DESTINATARI = tuple(
    indirizzo.strip()
    for indirizzo in os.getenv("CONSUMER_EMAIL_DESTINATARI", "").split(";")
    if indirizzo.strip()
)
# Se true: non invia email, non carica il report su SharePoint, non elimina i
# file RAW e salva il report nella cartella "output" accanto al codice.
TEST_RUN = os.getenv("CONSUMER_TEST_RUN", "true").strip().casefold()
if TEST_RUN not in {"true", "false"}:
    raise ValueError("CONSUMER_TEST_RUN deve essere 'true' oppure 'false'")
TEST_RUN = TEST_RUN == "true"

# Microsoft Graph - applicazione dedicata alle automazioni SharePoint.
SHAREPOINT_GRAPH_CLIENT_ID = os.getenv("SHAREPOINT_GRAPH_CLIENT_ID", "").strip()
SHAREPOINT_GRAPH_TENANT_ID = os.getenv("SHAREPOINT_GRAPH_TENANT_ID", "").strip()
SHAREPOINT_GRAPH_CLIENT_SECRET = os.getenv(
    "SHAREPOINT_GRAPH_CLIENT_SECRET", ""
).strip()

# Origine remota dei file RAW nel sito MyWay Tools.
SHAREPOINT_RAW_HOSTNAME = os.getenv("SHAREPOINT_HOSTNAME", "mywaysrl.sharepoint.com").strip()
SHAREPOINT_RAW_SITE_PATH = os.getenv("SHAREPOINT_MYWAY_TOOLS_SITE_PATH", "/sites/MyWayTools").strip()
SHAREPOINT_RAW_LIBRARY_NAME = os.getenv("SHAREPOINT_MYWAY_TOOLS_LIBRARY_NAME", "Shared Documents").strip()
SHAREPOINT_RAW_FOLDER = os.getenv(
    "SHAREPOINT_RAW_FOLDER", "MyWay Tools/SCRIPT/00_RAW_FILE"
).strip(" /")

# Destinazione remota del report nel sito 00_SCAMBIODOCUMENTI.
SHAREPOINT_HOSTNAME = os.getenv(
    "SHAREPOINT_HOSTNAME", "mywaysrl.sharepoint.com"
).strip()
SHAREPOINT_SITE_PATH = os.getenv(
    "SHAREPOINT_SCAMBIO_SITE_PATH", "/sites/00_SCAMBIODOCUMENTI"
).strip()
SHAREPOINT_LIBRARY_NAME = os.getenv(
    "SHAREPOINT_SCAMBIO_LIBRARY_NAME", "Shared Documents"
).strip()
SHAREPOINT_OUTPUT_FOLDER = os.getenv(
    "SHAREPOINT_CONSUMER_DAILY_REPORT_FOLDER",
    "00_SCAMBIO DOCUMENTI/CONSUMER/CRUSCOTTO GIORNALIERO",
).strip(" /")
