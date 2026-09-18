import json
import os
import sys
from datetime import datetime
from pathlib import Path

from colorama import Fore, init

init(autoreset=True)

BUSINESS_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = BUSINESS_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from graph_sharepoint import GraphSharePointClient

SHAREPOINT_HOSTNAME = os.getenv("SHAREPOINT_HOSTNAME", "").strip()
SHAREPOINT_SCAMBIO_SITE_PATH = os.getenv("SHAREPOINT_SCAMBIO_SITE_PATH", "").strip()
SHAREPOINT_SCAMBIO_LIBRARY_NAME = os.getenv("SHAREPOINT_SCAMBIO_LIBRARY_NAME", "").strip()
PATH_INPUT_PARQUET = os.getenv("SHAREPOINT_SCAMBIO_PARQUET_FOLDER", "").strip(" /")
PATH_OUTPUT_FCST = "siti SharePoint personali dei venditori"
CATALOGO_VENDITORI = BUSINESS_DIR / "config" / "venditori.json"

RICERCA_FILES = ["gara", "opportunita", "appuntamenti"]
PERIODO_GARE = {
    1: "Gen - Mar", 2: "Gen - Mar", 3: "Gen - Mar",
    4: "Apr - Giu", 5: "Apr - Giu", 6: "Apr - Giu",
    7: "Lug - Set", 8: "Lug - Set", 9: "Lug - Set",
    10: "Ott - Dic", 11: "Ott - Dic", 12: "Ott - Dic",
}
MESI_IT = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
    5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
    9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre",
}

_GRAPH_CLIENT = None
_DRIVE_SCAMBIO_ID = None
_DRIVE_VENDITORI = {}


def _client_graph():
    global _GRAPH_CLIENT
    if _GRAPH_CLIENT is None:
        _GRAPH_CLIENT = GraphSharePointClient()
    return _GRAPH_CLIENT


def _drive_scambio():
    global _DRIVE_SCAMBIO_ID
    configurazione = {
        "SHAREPOINT_HOSTNAME": SHAREPOINT_HOSTNAME,
        "SHAREPOINT_SCAMBIO_SITE_PATH": SHAREPOINT_SCAMBIO_SITE_PATH,
        "SHAREPOINT_SCAMBIO_LIBRARY_NAME": SHAREPOINT_SCAMBIO_LIBRARY_NAME,
        "SHAREPOINT_SCAMBIO_PARQUET_FOLDER": PATH_INPUT_PARQUET,
    }
    mancanti = [nome for nome, valore in configurazione.items() if not valore]
    if mancanti:
        raise ValueError("Configurazione SharePoint FCST incompleta: " + ", ".join(mancanti))
    if _DRIVE_SCAMBIO_ID is None:
        client = _client_graph()
        sito = client.trova_sito(SHAREPOINT_HOSTNAME, SHAREPOINT_SCAMBIO_SITE_PATH)
        raccolta = client.trova_raccolta_documenti(
            sito["id"], SHAREPOINT_SCAMBIO_LIBRARY_NAME
        )
        _DRIVE_SCAMBIO_ID = str(raccolta["id"])
    return _client_graph(), _DRIVE_SCAMBIO_ID


def _configurazione_venditore(venditore: str) -> dict:
    dati = json.loads(CATALOGO_VENDITORI.read_text(encoding="utf-8"))
    nome = str(venditore).strip().upper()
    for elemento in dati.get("venditori", []):
        if str(elemento.get("nome_crm", "")).strip().upper() == nome:
            richiesti = ("sharepoint_site_path", "sharepoint_library", "sharepoint_fcst_folder")
            mancanti = [campo for campo in richiesti if not elemento.get(campo)]
            if mancanti:
                raise ValueError(
                    f"Destinazione SharePoint FCST non configurata per {venditore}: "
                    + ", ".join(mancanti)
                )
            return elemento
    raise KeyError(f"Venditore non presente nel catalogo: {venditore}")


def _drive_venditore(venditore: str):
    configurazione = _configurazione_venditore(venditore)
    site_path = str(configurazione["sharepoint_site_path"])
    if site_path not in _DRIVE_VENDITORI:
        client = _client_graph()
        sito = client.trova_sito(SHAREPOINT_HOSTNAME, site_path)
        raccolta = client.trova_raccolta_documenti(
            sito["id"], configurazione["sharepoint_library"]
        )
        _DRIVE_VENDITORI[site_path] = str(raccolta["id"])
    return _client_graph(), _DRIVE_VENDITORI[site_path], configurazione


def trova_file(path: str, param: str) -> dict:
    client, drive_id = _drive_scambio()
    ricerca = param.strip().casefold()
    candidati = [
        file for file in client.elenca_file_cartella(drive_id, path)
        if ricerca in str(file.get("name", "")).casefold()
    ]
    if not candidati:
        raise FileNotFoundError(f"File {param!r} non presente in SharePoint: {path}")
    candidati.sort(key=lambda file: str(file.get("lastModifiedDateTime", "")), reverse=True)
    scelto = candidati[0]
    print(Fore.GREEN + "OK " + Fore.RESET + str(scelto.get("name")))
    return {**scelto, "content": client.scarica_file(drive_id, scelto["id"])}


def carica_report_venditore(venditore: str, nome_file: str, contenuto: bytes) -> dict:
    client, drive_id, configurazione = _drive_venditore(venditore)
    return client.carica_bytes(
        drive_id,
        configurazione["sharepoint_fcst_folder"],
        nome_file,
        contenuto,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def trova_periodo_gara():
    oggi = datetime.today()
    anno = oggi.year
    gara_corrente = PERIODO_GARE[oggi.month]
    if gara_corrente == "Gen - Mar":
        mesi = [1, 2, 3]
    elif gara_corrente == "Apr - Giu":
        mesi = [4, 5, 6]
    elif gara_corrente == "Lug - Set":
        mesi = [7, 8, 9]
    else:
        mesi = [10, 11, 12]
    return anno, mesi, gara_corrente
