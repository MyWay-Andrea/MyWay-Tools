from __future__ import annotations

import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


CARTELLA_SCRIPT = Path(__file__).resolve().parent
if str(CARTELLA_SCRIPT) not in sys.path:
    sys.path.insert(0, str(CARTELLA_SCRIPT))

from config import (
    FILE_NEGOZI,
    GIACENZE_TEST_RUN,
    INTESTAZIONE_CODICE_ARTICOLO,
    INTESTAZIONE_DESCRIZIONE,
    INTESTAZIONE_TOTALE_GIACENZA,
    INTESTAZIONE_TOTALE_VALORE,
    NOME_FILE_OUTPUT,
    PAROLE_CHIAVE_FILE,
    PATH_OUTPUT_TEST,
    SHAREPOINT_RAW_FOLDER,
    SHAREPOINT_RAW_HOSTNAME,
    SHAREPOINT_RAW_LIBRARY_NAME,
    SHAREPOINT_RAW_SITE_PATH,
    SUFFISSO_COLONNA_GIACENZA,
)
from leggi_giacenze import (
    carica_codici_negozi,
    estrai_dataframe_giacenze,
)
from crea_report import crea_report_giacenze

CARTELLA_SCRIPT_GENERALE = CARTELLA_SCRIPT.parents[1]
percorso_generale = str(CARTELLA_SCRIPT_GENERALE)
while percorso_generale in sys.path:
    sys.path.remove(percorso_generale)
sys.path.insert(0, percorso_generale)
sys.modules.pop("graph_sharepoint", None)
from graph_sharepoint import GraphSharePointClient


def _cerca_file_giacenze(
    client: GraphSharePointClient,
    drive_id: str,
    percorso_cartella: str,
    parole_chiave: tuple[str, ...],
) -> list[dict[str, Any]]:
    parole = tuple(parola.casefold() for parola in parole_chiave)
    estensioni_excel = {".xlsx", ".xlsm"}
    file_trovati = [
        elemento
        for elemento in client.elenca_file_cartella(drive_id, percorso_cartella)
        if all(
            parola in Path(str(elemento.get("name", ""))).stem.casefold()
            for parola in parole
        )
        and Path(str(elemento.get("name", ""))).suffix.casefold()
        in estensioni_excel
        and not str(elemento.get("name", "")).startswith("~$")
    ]
    return sorted(
        file_trovati,
        key=lambda elemento: str(elemento.get("lastModifiedDateTime", "")),
        reverse=True,
    )


def _estrai_timestamp_nome(nome_file: str) -> str:
    """Converte la data del RAW da GG_MM_AAAA a AAAAMMGG."""

    corrispondenza = re.search(r"(?:^|_)(\d{2})_(\d{2})_(\d{4})(?:\D|$)", nome_file)
    if not corrispondenza:
        raise ValueError(f"Data non riconosciuta nel nome del RAW: {nome_file}")
    giorno, mese, anno = corrispondenza.groups()
    data_file = datetime.strptime(f"{giorno}_{mese}_{anno}", "%d_%m_%Y")
    return data_file.strftime("%Y%m%d")


def _seleziona_file_remoto(file_trovati: list[dict[str, Any]]) -> dict[str, Any]:
    if not file_trovati:
        raise FileNotFoundError(
            f"Nessun file GIACENZE_ARTICOLI trovato in {SHAREPOINT_RAW_FOLDER}"
        )
    if len(file_trovati) > 1:
        print(
            f"ATTENZIONE: trovati {len(file_trovati)} file di giacenza. "
            f"Uso il più recente: {file_trovati[0]['name']}"
        )
    return file_trovati[0]


def elimina_file_raw(
    client: GraphSharePointClient,
    drive_id: str,
    file_remoto: dict[str, Any],
) -> None:
    """Elimina esclusivamente il RAW elaborato, verificandone drive ed eTag."""

    item_id = str(file_remoto.get("id", "")).strip()
    etag = str(file_remoto.get("eTag", "")).strip()
    nome_file = str(file_remoto.get("name", "")).strip()
    drive_elemento = str(
        file_remoto.get("parentReference", {}).get("driveId", "")
    ).strip()
    if not item_id or not etag or not nome_file:
        raise ValueError(f"Metadati Graph incompleti per il RAW: {nome_file!r}")
    if drive_elemento and drive_elemento != drive_id:
        raise ValueError(
            f"Eliminazione bloccata per {nome_file}: drive Graph non coerente"
        )
    client.elimina_file(drive_id, item_id, etag)
    print(f"✓ File RAW eliminato da SharePoint: {nome_file}")


def finalizza_pipeline(
    percorso_report: Path,
    client: GraphSharePointClient,
    drive_id: str,
    file_remoto: dict[str, Any],
) -> None:
    """Elimina il RAW solo dopo la creazione verificata del report."""

    percorso_report = Path(percorso_report)
    if not percorso_report.is_file() or percorso_report.stat().st_size == 0:
        raise FileNotFoundError(
            f"Eliminazione RAW bloccata: report non creato o vuoto ({percorso_report})"
        )
    if GIACENZE_TEST_RUN:
        print("TEST RUN: eliminazione del file RAW saltata")
        return
    elimina_file_raw(client, drive_id, file_remoto)


def prepara_dati() -> tuple[
    pd.DataFrame,
    Path,
    GraphSharePointClient,
    str,
    dict[str, Any],
]:
    """Scarica il RAW da SharePoint e prepara il DataFrame del futuro report."""

    print("\n→ Lettura configurazione negozi...")
    codici_negozi = carica_codici_negozi(FILE_NEGOZI)
    print(f"✓ Negozi configurati: {len(codici_negozi)}")

    print("\n→ Connessione a SharePoint e ricerca file RAW...")
    client = GraphSharePointClient()
    sito = client.trova_sito(SHAREPOINT_RAW_HOSTNAME, SHAREPOINT_RAW_SITE_PATH)
    raccolta = client.trova_raccolta_documenti(
        sito["id"], SHAREPOINT_RAW_LIBRARY_NAME
    )
    drive_id = str(raccolta["id"])
    file_trovati = _cerca_file_giacenze(
        client,
        drive_id,
        SHAREPOINT_RAW_FOLDER,
        PAROLE_CHIAVE_FILE,
    )
    file_remoto = _seleziona_file_remoto(file_trovati)
    nome_file = str(file_remoto["name"])
    print(f"✓ File selezionato: {nome_file}")

    print("\n→ Download file RAW in memoria...")
    contenuto = client.scarica_file(drive_id, str(file_remoto["id"]))
    print(f"✓ Scaricati {len(contenuto)} byte")

    print("\n→ Lettura e preparazione dati...")
    dataframe = estrai_dataframe_giacenze(
        contenuto,
        codici_negozi,
        nome_file=nome_file,
        intestazione_codice=INTESTAZIONE_CODICE_ARTICOLO,
        intestazione_descrizione=INTESTAZIONE_DESCRIZIONE,
        suffisso_giacenza=SUFFISSO_COLONNA_GIACENZA,
        intestazione_totale=INTESTAZIONE_TOTALE_GIACENZA,
        intestazione_totale_valore=INTESTAZIONE_TOTALE_VALORE,
    )
    print(f"✓ Articoli estratti: {len(dataframe)}")
    print(f"✓ Colonne pronte: {', '.join(dataframe.columns)}")

    timestamp = _estrai_timestamp_nome(nome_file)
    percorso_output = PATH_OUTPUT_TEST / NOME_FILE_OUTPUT.format(timestamp=timestamp)
    print("\n→ Creazione report Excel di test...")
    percorso_output = crea_report_giacenze(dataframe, percorso_output)
    print(f"✓ Report di test creato: {percorso_output}")
    print("TEST: upload SharePoint ed eliminazione RAW non eseguiti.")
    return dataframe, percorso_output, client, drive_id, file_remoto


def main() -> None:
    prepara_dati()


if __name__ == "__main__":
    main()
