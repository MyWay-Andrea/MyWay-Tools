import sys
import time
from io import BytesIO
from datetime import datetime

import pandas as pd
from colorama import Fore, init

from archivio_storico import (
    aggiorna_archivio,
    archivio_valido,
    chiudi_periodi_precedenti,
    leggi_archivio,
    prepara_blocco,
    riepilogo_archivio,
    salva_archivio_atomico,
    vista_excel,
)
from config import (
    FILE_STORICO_GARA_PARQUET,
    PATH_BASI_DATI,
    PATH_BACKUP_STORICO_GARA_XLSX,
    PATH_STORICO_BASI_DATI,
    PATH_STORICO_PARQUET,
    carica_su_teams,
    carica_file_sharepoint,
    elenca_file_sharepoint,
    scarica_file_sharepoint,
    trova_file,
    trova_periodo_gara,
)
from estrai_gara_API import main as importa_df_gara
from formatta_gara import main as elabora_gara

init(autoreset=True)


def _backup_excel(file_storico):
    if not file_storico:
        return None
    timestamp = datetime.now().strftime("%Y%m%d")
    return carica_file_sharepoint(
        PATH_BACKUP_STORICO_GARA_XLSX,
        f"Storico Gara_{timestamp}.xlsx",
        file_storico["content"],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _trova_chiusura_apr_giu():
    candidati = [
        file for file in elenca_file_sharepoint(PATH_BASI_DATI, crea=True)
        if "chiusura_gara_" in str(file.get("name", "")).casefold()
        and "apr_giu" in str(file.get("name", "")).casefold()
        and str(file.get("name", "")).casefold().endswith(".xlsx")
    ]
    candidati.sort(
        key=lambda file: str(file.get("lastModifiedDateTime", "")), reverse=True
    )
    if not candidati:
        raise FileNotFoundError(
            "File CHIUSURA_GARA_Apr_Giu.xlsx non trovato in "
            f"{PATH_BASI_DATI}"
        )
    scelto = candidati[0]
    return scarica_file_sharepoint(PATH_BASI_DATI, scelto["name"])


def _inizializza_archivio(df_gara, file_storico):
    print("Prima inizializzazione dell'archivio tecnico...")
    storico_excel = pd.read_excel(BytesIO(file_storico["content"]), dtype=str)

    # Le righe del nuovo CRM presenti nell'Excel sono sostituite dall'estrazione
    # API, che conserva l'ID Riga CRM necessario all'upsert.
    mask_nuovo_crm = storico_excel[
        "ID ordine (Ordine)"
    ].astype(str).str.startswith("TR4000", na=False)
    storico_legacy = storico_excel.loc[~mask_nuovo_crm].copy()

    file_chiusura = _trova_chiusura_apr_giu()
    print(f"Caricamento chiusura: {file_chiusura['name']}")
    chiusura_apr_giu = pd.read_excel(BytesIO(file_chiusura["content"]), dtype=str)

    blocco_legacy = prepara_blocco(
        storico_legacy,
        fonte="STORICO_LEGACY",
        stato_archivio="CHIUSO",
    )
    blocco_chiusura = prepara_blocco(
        chiusura_apr_giu,
        fonte="CHIUSURA_GARA",
        stato_archivio="CHIUSO",
        anno_default=datetime.today().year,
        trimestre_default=2,
    )

    inizio, _, _ = trova_periodo_gara()
    blocco_api = prepara_blocco(
        df_gara,
        fonte="API",
        stato_archivio="CORRENTE",
        anno_default=inizio.year,
        trimestre_default=((inizio.month - 1) // 3) + 1,
    )

    archivio = pd.concat(
        [blocco_legacy, blocco_chiusura, blocco_api],
        ignore_index=True,
    )
    if archivio["Chiave Archivio"].duplicated().any():
        duplicati = archivio.loc[
            archivio["Chiave Archivio"].duplicated(keep=False),
            "Chiave Archivio",
        ].unique()
        raise ValueError(
            "Chiavi duplicate durante la migrazione: "
            + ", ".join(map(str, duplicati[:10]))
        )
    return archivio


def _carica_o_migra(df_gara, file_storico):
    remoto = scarica_file_sharepoint(
        PATH_STORICO_PARQUET,
        FILE_STORICO_GARA_PARQUET,
        obbligatorio=False,
    )
    if remoto:
        archivio_esistente = pd.read_parquet(BytesIO(remoto["content"]))
        if archivio_valido(archivio_esistente):
            inizio, _, _ = trova_periodo_gara()
            trimestre_corrente = ((inizio.month - 1) // 3) + 1
            blocco_api = prepara_blocco(
                df_gara,
                fonte="API",
                stato_archivio="CORRENTE",
                anno_default=inizio.year,
                trimestre_default=trimestre_corrente,
            )
            archivio_esistente = chiudi_periodi_precedenti(
                leggi_archivio(remoto["content"]),
                anno_corrente=inizio.year,
                trimestre_corrente=trimestre_corrente,
            )
            return aggiorna_archivio(
                archivio_esistente,
                blocco_api,
            )

        print(
            "Il vecchio Parquet non contiene lo schema tecnico: "
            "verrà salvato nel backup e sostituito tramite migrazione."
        )

    return _inizializza_archivio(df_gara, file_storico)


def main(df_gara, file_storico):
    start_script = time.perf_counter()
    df_gara = elabora_gara(df_gara)

    try:
        archivio = _carica_o_migra(df_gara, file_storico)
        backup = salva_archivio_atomico(archivio)
        backup_excel = _backup_excel(file_storico)
        carica_su_teams(vista_excel(archivio), PATH_STORICO_BASI_DATI)
    except Exception as exc:
        print(
            "[" + Fore.RED + "ERRORE" + Fore.RESET
            + f"] Aggiornamento archivio storico fallito --> {exc}"
        )
        raise

    print("\nRiepilogo archivio:")
    print(riepilogo_archivio(archivio).to_string(index=False))
    if backup:
        print(f"\nBackup creato: {backup['name']}")
    if backup_excel:
        print(f"Backup Excel creato: {backup_excel['name']}")
    print(f"Tempo di esecuzione: {time.perf_counter() - start_script:.2f} secondi")
    return archivio


if __name__ == "__main__":
    df_gara = importa_df_gara()
    file_storico = trova_file(PATH_STORICO_BASI_DATI, "Storico")
    main(df_gara, file_storico)
