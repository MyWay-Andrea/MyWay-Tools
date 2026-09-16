import hashlib
import os
import shutil
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from config import (
    COLONNE_CORRETTE_STORICO,
    FILE_STORICO_GARA_PARQUET,
    PATH_BACKUP_STORICO_GARA,
)


COLONNE_TECNICHE = [
    "ID Riga CRM",
    "Stato Ordine Tecnico",
    "Chiave Archivio",
    "Fonte Archivio",
    "Anno Gara",
    "Trimestre Gara",
    "Periodo Gara",
    "Stato Archivio",
    "Prima Estrazione",
    "Ultimo Aggiornamento",
    "Data Chiusura Gara",
]

SCHEMA_ARCHIVIO = COLONNE_CORRETTE_STORICO + COLONNE_TECNICHE
PERIODI = {
    1: "Gen - Mar",
    2: "Apr - Giu",
    3: "Lug - Set",
    4: "Ott - Dic",
}


def _converti_data(serie):
    def converti(valore):
        if pd.isna(valore):
            return pd.NaT
        if isinstance(valore, (pd.Timestamp, datetime, date)):
            return pd.Timestamp(valore)
        testo = str(valore).strip()
        if (
            len(testo) >= 10
            and testo[4] == "-"
            and testo[7] == "-"
            and testo[:4].isdigit()
        ):
            return pd.to_datetime(testo, errors="coerce")
        return pd.to_datetime(
            testo,
            format="mixed",
            dayfirst=True,
            errors="coerce",
        )

    return pd.to_datetime(serie.map(converti), errors="coerce")


def _testo_chiave(valore):
    if pd.isna(valore):
        return ""
    if isinstance(valore, (pd.Timestamp, datetime)):
        return valore.strftime("%Y-%m-%d")
    return str(valore).strip()


def _hash_riga(row):
    campi = [
        "ID ordine (Ordine)",
        "ID Pratica",
        "Prodotto esistente",
        "Data creazione",
        "Data Inserimento OmniSales",
        "Data Attivazione",
        "Importo totale",
        "Proprietario (Ordine)",
    ]
    testo = "|".join(_testo_chiave(row.get(campo)) for campo in campi)
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()[:24]


def _normalizza_colonne_base(df):
    risultato = df.copy()
    risultato = risultato.drop(columns=["Stato Ordine"], errors="ignore")

    mancanti = [
        colonna for colonna in COLONNE_CORRETTE_STORICO
        if colonna not in risultato.columns
    ]
    if mancanti:
        raise ValueError(
            "Colonne mancanti per l'archivio storico: "
            + ", ".join(mancanti)
        )

    for colonna in COLONNE_CORRETTE_STORICO:
        if "Data" in colonna:
            risultato[colonna] = _converti_data(risultato[colonna])
        elif (
            "Quantit" in colonna
            or "scont" in colonna.lower()
        ):
            risultato[colonna] = pd.to_numeric(
                risultato[colonna], errors="coerce"
            ).fillna(0).astype("Int64")
        elif "Prezzo" in colonna or "Importo" in colonna:
            risultato[colonna] = pd.to_numeric(
                risultato[colonna], errors="coerce"
            ).astype("Float64")
        else:
            risultato[colonna] = risultato[colonna].astype("string")

    return risultato


def _assegna_periodo(df, anno_default=None, trimestre_default=None):
    risultato = df.copy()
    data_attivazione = pd.to_datetime(
        risultato["Data Attivazione"], errors="coerce"
    )

    anno = data_attivazione.dt.year.astype("Int64")
    trimestre = data_attivazione.dt.quarter.astype("Int64")

    if anno_default is not None:
        anno = anno.fillna(int(anno_default))
    if trimestre_default is not None:
        trimestre = trimestre.fillna(int(trimestre_default))

    risultato["Anno Gara"] = anno
    risultato["Trimestre Gara"] = trimestre
    risultato["Periodo Gara"] = trimestre.map(PERIODI)
    return risultato


def normalizza_schema_archivio(df):
    risultato = df.copy()
    for colonna in COLONNE_CORRETTE_STORICO:
        if "Data" in colonna:
            risultato[colonna] = _converti_data(risultato[colonna])
        elif "Quantit" in colonna or "scont" in colonna.lower():
            risultato[colonna] = pd.to_numeric(
                risultato[colonna], errors="coerce"
            ).fillna(0).astype("Int64")
        elif "Prezzo" in colonna or "Importo" in colonna:
            risultato[colonna] = pd.to_numeric(
                risultato[colonna], errors="coerce"
            ).astype("Float64")
        else:
            risultato[colonna] = risultato[colonna].astype("string")

    for colonna in (
        "ID Riga CRM",
        "Stato Ordine Tecnico",
        "Chiave Archivio",
        "Fonte Archivio",
        "Periodo Gara",
        "Stato Archivio",
    ):
        risultato[colonna] = risultato[colonna].astype("string")
    for colonna in ("Anno Gara", "Trimestre Gara"):
        risultato[colonna] = pd.to_numeric(
            risultato[colonna], errors="coerce"
        ).astype("Int64")
    for colonna in (
        "Prima Estrazione",
        "Ultimo Aggiornamento",
        "Data Chiusura Gara",
    ):
        risultato[colonna] = pd.to_datetime(
            risultato[colonna], errors="coerce"
        )
    return risultato[SCHEMA_ARCHIVIO]


def prepara_blocco(
    df,
    fonte,
    stato_archivio,
    data_elaborazione=None,
    anno_default=None,
    trimestre_default=None,
):
    adesso = pd.Timestamp(data_elaborazione or datetime.now())
    stato_ordine = (
        df["Stato Ordine"].copy()
        if "Stato Ordine" in df.columns
        else pd.Series(pd.NA, index=df.index, dtype="string")
    )
    id_riga = (
        df["ID Riga CRM"].copy()
        if "ID Riga CRM" in df.columns
        else pd.Series(pd.NA, index=df.index, dtype="string")
    )

    risultato = _normalizza_colonne_base(df)
    risultato["ID Riga CRM"] = id_riga.astype("string")
    risultato["Stato Ordine Tecnico"] = stato_ordine.astype("string")
    risultato = _assegna_periodo(
        risultato,
        anno_default=anno_default,
        trimestre_default=trimestre_default,
    )

    id_pulito = risultato["ID Riga CRM"].fillna("").str.strip()
    hash_base = risultato.apply(_hash_riga, axis=1)
    occorrenza = hash_base.groupby(hash_base).cumcount().astype(str)
    risultato["Chiave Archivio"] = (
        "LEGACY:" + hash_base + ":" + occorrenza
    )
    mask_crm = id_pulito.ne("")
    risultato.loc[mask_crm, "Chiave Archivio"] = (
        "CRM:" + id_pulito[mask_crm]
    )

    risultato["Fonte Archivio"] = fonte
    risultato["Stato Archivio"] = stato_archivio
    risultato["Prima Estrazione"] = adesso
    risultato["Ultimo Aggiornamento"] = adesso
    risultato["Data Chiusura Gara"] = (
        adesso if stato_archivio == "CHIUSO" else pd.NaT
    )
    return risultato[SCHEMA_ARCHIVIO]


def archivio_valido(df):
    return set(SCHEMA_ARCHIVIO).issubset(df.columns)


def leggi_archivio(path=FILE_STORICO_GARA_PARQUET):
    archivio = pd.read_parquet(path)
    if not archivio_valido(archivio):
        raise ValueError(
            f"Il file {path} non usa ancora lo schema tecnico dell'archivio."
        )
    return normalizza_schema_archivio(archivio)


def aggiorna_archivio(archivio, blocco_api):
    if archivio["Chiave Archivio"].duplicated().any():
        raise ValueError("L'archivio contiene Chiavi Archivio duplicate.")
    if blocco_api["Chiave Archivio"].duplicated().any():
        duplicati = blocco_api.loc[
            blocco_api["Chiave Archivio"].duplicated(keep=False),
            "Chiave Archivio",
        ].unique()
        raise ValueError(
            "L'API ha restituito ID Riga CRM duplicati: "
            + ", ".join(map(str, duplicati[:10]))
        )

    api = blocco_api.set_index("Chiave Archivio")
    storico = archivio.set_index("Chiave Archivio")
    chiavi_esistenti = storico.index.intersection(api.index)

    if len(chiavi_esistenti):
        prima_estrazione = storico.loc[chiavi_esistenti, "Prima Estrazione"]
        for colonna in SCHEMA_ARCHIVIO:
            if colonna not in ("Chiave Archivio", "Prima Estrazione"):
                storico.loc[chiavi_esistenti, colonna] = api.loc[
                    chiavi_esistenti, colonna
                ]
        storico.loc[chiavi_esistenti, "Prima Estrazione"] = prima_estrazione

    nuove = api.loc[~api.index.isin(storico.index)]
    aggiornato = pd.concat([storico, nuove], axis=0).reset_index()

    if len(aggiornato) < len(archivio):
        raise ValueError(
            "Controllo di sicurezza fallito: il numero di righe è diminuito."
        )
    if aggiornato["Chiave Archivio"].duplicated().any():
        raise ValueError("Controllo di sicurezza fallito: chiavi duplicate.")

    return aggiornato[SCHEMA_ARCHIVIO]


def chiudi_periodi_precedenti(archivio, anno_corrente, trimestre_corrente):
    risultato = archivio.copy()
    periodo_numerico = (
        risultato["Anno Gara"].astype("Int64") * 10
        + risultato["Trimestre Gara"].astype("Int64")
    )
    periodo_corrente = int(anno_corrente) * 10 + int(trimestre_corrente)
    da_chiudere = (
        risultato["Stato Archivio"].eq("CORRENTE")
        & risultato["Data Attivazione"].notna()
        & periodo_numerico.lt(periodo_corrente)
    )
    risultato.loc[da_chiudere, "Stato Archivio"] = "CHIUSO"
    risultato.loc[da_chiudere, "Data Chiusura Gara"] = pd.Timestamp.now()
    return risultato[SCHEMA_ARCHIVIO]


def _backup(path):
    if not path.exists():
        return None
    PATH_BACKUP_STORICO_GARA.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destinazione = PATH_BACKUP_STORICO_GARA / (
        f"Storico Gara_{timestamp}.parquet"
    )
    shutil.copy2(path, destinazione)
    return destinazione


def salva_archivio_atomico(df, path=FILE_STORICO_GARA_PARQUET):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = _backup(path)
    temporaneo = path.with_name(f".{path.stem}.tmp{path.suffix}")

    df = normalizza_schema_archivio(df)
    try:
        df.to_parquet(temporaneo, index=False)
        verifica = pd.read_parquet(temporaneo)
        if len(verifica) != len(df) or not archivio_valido(verifica):
            raise ValueError("Verifica del Parquet temporaneo fallita.")
        os.replace(temporaneo, path)
    finally:
        if temporaneo.exists():
            temporaneo.unlink()

    return backup


def vista_excel(archivio):
    return archivio[COLONNE_CORRETTE_STORICO].copy()


def riepilogo_archivio(archivio):
    return (
        archivio.groupby(
            ["Anno Gara", "Trimestre Gara", "Periodo Gara", "Stato Archivio"],
            dropna=False,
        )
        .size()
        .rename("Righe")
        .reset_index()
    )
