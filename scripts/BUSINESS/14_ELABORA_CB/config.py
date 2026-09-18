from pathlib import Path
import tempfile
import os
import sys

CARTELLA_BUSINESS = Path(__file__).parents[1]
SCRIPT_DIR = CARTELLA_BUSINESS.parent

if str(CARTELLA_BUSINESS) not in sys.path:
    sys.path.insert(0, str(CARTELLA_BUSINESS))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common.venditori import leggi_venditori as leggi_commerciali
import config_env  # noqa: E402,F401
COMMERCIALI = leggi_commerciali()


def leggi_booleano_env(nome: str, predefinito: str) -> bool:
    valore = os.getenv(nome, predefinito).strip().lower()

    if valore not in {"true", "false"}:
        raise ValueError(
            f"Valore non valido per {nome}: {valore!r}. "
            "Usa esclusivamente 'true' oppure 'false'."
        )

    return valore == "true"


#configurazione API CRM 
BASE_URL = "https://app.crmincloud.it/api/v1"
API_KEY = os.getenv("CRM_REPORTISTICA_API_KEY_CB")
GOVERNANCE_EMAIL = os.getenv("GOVERNANCE_EMAIL", "")
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID", "")
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID", "")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET", "")
GRAPH_SENDER_EMAIL = os.getenv("GRAPH_SENDER_EMAIL", "")
CRM_DRY_RUN = leggi_booleano_env("CRM_DRY_RUN", "false")
EMAIL_DRY_RUN = leggi_booleano_env("EMAIL_DRY_RUN", "true")
CB_RAPIDA = leggi_booleano_env("CB_RAPIDA", "false")

# Alias mantenuto per compatibilità con eventuali import esterni esistenti.
DRY_RUN = CRM_DRY_RUN


def stampa_stato_dry_run() -> None:
    print("\nStato modalità dry-run:")
    print(f"  CRM_DRY_RUN   : {CRM_DRY_RUN}")
    print(f"  EMAIL_DRY_RUN : {EMAIL_DRY_RUN}")
    print(f"  CB_RAPIDA     : {CB_RAPIDA}")

# SharePoint CB: percorso dedicato e indipendente dalle basi dati Excel.
SHAREPOINT_HOSTNAME = os.getenv("SHAREPOINT_HOSTNAME", "").strip()
SHAREPOINT_SCAMBIO_SITE_PATH = os.getenv("SHAREPOINT_SCAMBIO_SITE_PATH", "").strip()
SHAREPOINT_SCAMBIO_LIBRARY_NAME = os.getenv("SHAREPOINT_SCAMBIO_LIBRARY_NAME", "").strip()
PATH_CB_FOLDER = os.getenv("SHAREPOINT_BUSINESS_CB_FOLDER", "").strip(" /")
PATH_RAW_CB_REMOTO = f"{PATH_CB_FOLDER}/00_DA_ELABORARE"
PATH_CB_CORRENTE_REMOTO = f"{PATH_CB_FOLDER}/01_CORRENTE"
PATH_CB_STORICO_REMOTO = f"{PATH_CB_FOLDER}/99_STORICO"

# Area temporanea locale: serve solo durante l'esecuzione per pandas, allegati e log.
PATH_CB_TEMP = Path(tempfile.mkdtemp(prefix="myway_cb_"))
PATH_RAW_CB = PATH_CB_TEMP / "00_DA_ELABORARE"
PATH_CB_CORRENTE = PATH_CB_TEMP / "01_CORRENTE"
PATH_CB_STORICO = PATH_CB_TEMP / "99_STORICO"
