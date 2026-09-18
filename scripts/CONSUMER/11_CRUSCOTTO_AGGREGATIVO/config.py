from __future__ import annotations

import os
import sys
from pathlib import Path


CARTELLA_CONSUMER = Path(__file__).resolve().parents[1]
if str(CARTELLA_CONSUMER) not in sys.path:
    sys.path.insert(0, str(CARTELLA_CONSUMER))

CARTELLA_SCRIPT = Path(__file__).resolve().parents[2]
if str(CARTELLA_SCRIPT) not in sys.path:
    sys.path.append(str(CARTELLA_SCRIPT))

import config_env  # noqa: E402,F401

from common.negozi import (  # noqa: E402
    carica_negozi,
)


NOME_OUTPUT = "CRUSCOTTO.xlsx"

# Il file config/negozi.json e' la fonte per elenco e ordine dei negozi.
# EXTRA aggrega gli inserimenti non associati a un negozio configurato.
ORDINE_NEGOZI = [*carica_negozi(), "EXTRA"]

MAPPA_PEDONALITA = {
    "Carpi": "CARPI",
    "Fidenza": "FIDENZA",
    "Parma Eurosia": "EUROSIA",
    "Parma Torri": "TORRI",
    "Piacenza Galassia": "GALASSIA",
    "Sassuolo": "SASSUOLO",
}

CROSS_SELLING = "SOLO GADGET"

SHAREPOINT_HOSTNAME = os.getenv("SHAREPOINT_HOSTNAME", "").strip()
SHAREPOINT_NEGOZI_LIBRARY_NAME = os.getenv(
    "SHAREPOINT_NEGOZI_LIBRARY_NAME",
    "Documents",
).strip()
SHAREPOINT_NEGOZI_SITE_PATHS = {
    negozio: os.getenv(f"SHAREPOINT_{negozio}_SITE_PATH", "").strip()
    for negozio in carica_negozi()
}
SHAREPOINT_TEAM_CONSUMER_SITE_PATH = os.getenv(
    "SHAREPOINT_TEAM_CONSUMER_SITE_PATH", ""
).strip()
SHAREPOINT_CONSUMER_MANDELLI_SITE_PATH = os.getenv(
    "SHAREPOINT_CONSUMER_MANDELLI_SITE_PATH", ""
).strip()
SHAREPOINT_SCAMBIO_SITE_PATH = os.getenv(
    "SHAREPOINT_SCAMBIO_SITE_PATH", ""
).strip()
SHAREPOINT_CONSUMER_LIBRARY_NAME = os.getenv(
    "SHAREPOINT_CONSUMER_LIBRARY_NAME", "Documents"
).strip()
SHAREPOINT_PEDONALITA_FOLDER = os.getenv(
    "SHAREPOINT_SCAMBIO_PARQUET_FOLDER", ""
).strip(" /")
SHAREPOINT_CRUSCOTTO_AGGREGATIVO_OUTPUT_FOLDER = os.getenv(
    "SHAREPOINT_CRUSCOTTO_AGGREGATIVO_OUTPUT_FOLDER", ""
).strip(" /")


def _file_esatto(client_sharepoint, drive_id: str, nome_file: str) -> dict:
    candidati = [
        elemento
        for elemento in client_sharepoint.cerca_file(drive_id, nome_file)
        if str(elemento.get("name", "")).casefold() == nome_file.casefold()
    ]
    if not candidati:
        raise FileNotFoundError(f"File {nome_file!r} non trovato su SharePoint")
    candidati.sort(
        key=lambda elemento: str(elemento.get("lastModifiedDateTime", "")),
        reverse=True,
    )
    if len(candidati) > 1:
        print(f"Attenzione: trovati {len(candidati)} file {nome_file}; uso il piu recente")
    selezionato = candidati[0]
    selezionato["drive_id"] = drive_id
    return selezionato


def trova_sorgenti(client_sharepoint) -> dict[str, object]:
    mancanti = [
        f"SHAREPOINT_{negozio}_SITE_PATH"
        for negozio, percorso in SHAREPOINT_NEGOZI_SITE_PATHS.items()
        if not percorso
    ]
    if not SHAREPOINT_HOSTNAME:
        mancanti.insert(0, "SHAREPOINT_HOSTNAME")
    for nome, valore in {
        "SHAREPOINT_TEAM_CONSUMER_SITE_PATH": SHAREPOINT_TEAM_CONSUMER_SITE_PATH,
        "SHAREPOINT_CONSUMER_MANDELLI_SITE_PATH": SHAREPOINT_CONSUMER_MANDELLI_SITE_PATH,
        "SHAREPOINT_SCAMBIO_SITE_PATH": SHAREPOINT_SCAMBIO_SITE_PATH,
        "SHAREPOINT_CONSUMER_LIBRARY_NAME": SHAREPOINT_CONSUMER_LIBRARY_NAME,
        "SHAREPOINT_SCAMBIO_PARQUET_FOLDER": SHAREPOINT_PEDONALITA_FOLDER,
    }.items():
        if not valore:
            mancanti.append(nome)
    if mancanti:
        raise ValueError(
            "Configurazione SharePoint negozi incompleta: " + ", ".join(mancanti)
        )

    sito_team_consumer = client_sharepoint.trova_sito(
        SHAREPOINT_HOSTNAME,
        SHAREPOINT_TEAM_CONSUMER_SITE_PATH,
    )
    raccolta_team_consumer = client_sharepoint.trova_raccolta_documenti(
        sito_team_consumer["id"],
        SHAREPOINT_CONSUMER_LIBRARY_NAME,
    )
    business = _file_esatto(
        client_sharepoint,
        raccolta_team_consumer["id"],
        "BUSINESS GIORNALIERO.xlsx",
    )

    sito_scambio = client_sharepoint.trova_sito(
        SHAREPOINT_HOSTNAME,
        SHAREPOINT_SCAMBIO_SITE_PATH,
    )
    raccolta_scambio = client_sharepoint.trova_raccolta_documenti(
        sito_scambio["id"],
        SHAREPOINT_CONSUMER_LIBRARY_NAME,
    )
    candidati_pedonalita = [
        elemento
        for elemento in client_sharepoint.elenca_file_cartella(
            raccolta_scambio["id"],
            SHAREPOINT_PEDONALITA_FOLDER,
        )
        if str(elemento.get("name", "")).casefold().startswith("pedonalit")
        and str(elemento.get("name", "")).casefold().endswith(".parquet")
    ]
    if not candidati_pedonalita:
        raise FileNotFoundError("File Parquet Pedonalita non trovato su SharePoint")
    candidati_pedonalita.sort(
        key=lambda elemento: str(elemento.get("lastModifiedDateTime", "")),
        reverse=True,
    )
    pedonalita = candidati_pedonalita[0]
    pedonalita["drive_id"] = raccolta_scambio["id"]

    sito_consumer_mandelli = client_sharepoint.trova_sito(
        SHAREPOINT_HOSTNAME,
        SHAREPOINT_CONSUMER_MANDELLI_SITE_PATH,
    )
    raccolta_consumer_mandelli = client_sharepoint.trova_raccolta_documenti(
        sito_consumer_mandelli["id"],
        SHAREPOINT_CONSUMER_LIBRARY_NAME,
    )

    tracciamenti: dict[str, dict] = {}
    for negozio, site_path in SHAREPOINT_NEGOZI_SITE_PATHS.items():
        sito = client_sharepoint.trova_sito(SHAREPOINT_HOSTNAME, site_path)
        raccolta = client_sharepoint.trova_raccolta_documenti(
            sito["id"],
            SHAREPOINT_NEGOZI_LIBRARY_NAME,
        )
        nome_atteso = f"TRACCIAMENTO_{negozio}.xlsx"
        candidati = [
            elemento
            for elemento in client_sharepoint.cerca_file(
                raccolta["id"],
                f"TRACCIAMENTO_{negozio}",
            )
            if str(elemento.get("name", "")).casefold() == nome_atteso.casefold()
        ]
        if not candidati:
            raise FileNotFoundError(
                f"{nome_atteso} non trovato nel sito {sito['displayName']}"
            )
        candidati.sort(
            key=lambda elemento: str(elemento.get("lastModifiedDateTime", "")),
            reverse=True,
        )
        if len(candidati) > 1:
            print(
                f"Attenzione: trovati {len(candidati)} file {nome_atteso}; "
                "uso il piu recente"
            )
        selezionato = candidati[0]
        selezionato["drive_id"] = raccolta["id"]
        tracciamenti[negozio] = selezionato
        print(f"  OK {negozio}: {selezionato['name']}")

    return {
        "business": business,
        "pedonalita": pedonalita,
        "tracciamenti": tracciamenti,
        "destinazioni": {
            "TEAM CONSUMER": {
                "drive_id": raccolta_team_consumer["id"],
                "cartella": SHAREPOINT_CRUSCOTTO_AGGREGATIVO_OUTPUT_FOLDER,
            },
            "CONSUMER MANDELLI": {
                "drive_id": raccolta_consumer_mandelli["id"],
                "cartella": SHAREPOINT_CRUSCOTTO_AGGREGATIVO_OUTPUT_FOLDER,
            },
        },
    }
