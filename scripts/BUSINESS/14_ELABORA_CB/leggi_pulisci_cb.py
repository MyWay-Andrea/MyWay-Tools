from datetime import date, datetime
from pathlib import Path
import re

import pandas as pd

from config import COMMERCIALI, PATH_CB_CORRENTE
from cb_sharepoint import archivia_correnti, scarica_file_raw
from colonne_cb import trova_colonne_azienda
from console import avviso, dettaglio, info, percorso, successo
from consistenze import associa_colonne_cb


MESI_ITALIANI = (
    "gen", "feb", "mar", "apr", "mag", "giu",
    "lug", "ago", "set", "ott", "nov", "dic",
)


def trova_file_cb() -> Path:
    return scarica_file_raw(rapido=False)


def trova_file_cb_rapido() -> Path:
    """Restituisce l'unico file dati disponibile per una modifica massiva."""
    return scarica_file_raw(rapido=True)


def e_colonna_periodo(colonna) -> bool:
    if isinstance(colonna, (date, datetime, pd.Timestamp)):
        return True

    nome_colonna = str(colonna).strip().lower()
    mesi = "|".join(MESI_ITALIANI)
    formato_data = rf"^\d{{1,2}}\s+({mesi})\s+\d{{4}}$"

    return bool(re.match(formato_data, nome_colonna))


def trova_colonna_commerciale(df: pd.DataFrame):
    colonna = next(
        (colonna for colonna in df.columns if e_colonna_periodo(colonna)),
        None,
    )

    if colonna is None:
        raise ValueError("Non è stata trovata alcuna colonna periodo nel file CB")

    return colonna


def normalizza_testo(valore) -> str:
    return re.sub(r"\s+", " ", str(valore).strip()).casefold()


def crea_mappa_alias() -> dict[str, str]:
    mappa_alias = {}

    for commerciale in COMMERCIALI:
        nome_crm = commerciale["nome_crm"]
        mappa_alias[normalizza_testo(nome_crm)] = nome_crm

        for alias in commerciale["alias_cb"]:
            mappa_alias[normalizza_testo(alias)] = nome_crm

    return mappa_alias


def normalizza_colonna_commerciale(
    df: pd.DataFrame,
    colonna_commerciale,
) -> tuple[pd.DataFrame, list[str]]:
    mappa_alias = crea_mappa_alias()
    valori_non_riconosciuti = set()

    def sostituisci_alias(valore):
        if pd.isna(valore) or not str(valore).strip():
            return valore

        nome_normalizzato = normalizza_testo(valore)
        nome_crm = mappa_alias.get(nome_normalizzato)

        if nome_crm is None:
            valori_non_riconosciuti.add(str(valore).strip())
            return valore

        return nome_crm

    df = df.rename(columns={colonna_commerciale: "COMMERCIALE"})
    df["COMMERCIALE"] = df["COMMERCIALE"].apply(sostituisci_alias)

    return df, sorted(valori_non_riconosciuti, key=str.casefold)


def archivia_file_correnti() -> None:
    cartella_storico = archivia_correnti()
    if cartella_storico:
        successo("Vecchi file archiviati su SharePoint")
        percorso("Storico", cartella_storico)


def salva_file_correnti(file_cb: Path, df: pd.DataFrame) -> Path:
    PATH_CB_CORRENTE.mkdir(parents=True, exist_ok=True)

    copia_originale = PATH_CB_CORRENTE / file_cb.name
    file_pulito = PATH_CB_CORRENTE / f"{file_cb.stem}_PULITA.xlsx"

    copia_originale.write_bytes(file_cb.read_bytes())
    df.to_excel(file_pulito, index=False, engine="openpyxl")

    successo("File corrente aggiornato")
    percorso("Originale", copia_originale)
    percorso("Pulito", file_pulito)

    return file_pulito


def pulisci_dataframe_cb(file_cb: Path) -> pd.DataFrame:
    """Pulisce il file CB in memoria, senza creare o spostare file."""
    df = pd.read_excel(file_cb, dtype=str)

    colonna_commerciale = trova_colonna_commerciale(df)
    df, valori_non_riconosciuti = normalizza_colonna_commerciale(
        df,
        colonna_commerciale,
    )
    colonne_azienda = trova_colonne_azienda(df.columns)
    colonne_consistenze, campi_mancanti = associa_colonne_cb(df.columns)

    successo(f"File CB letto: {file_cb.name}")
    info(f"Colonna commerciale: {colonna_commerciale}")
    info(f"Colonne azienda: {colonne_azienda}")
    info(f"Campi consistenze riconosciuti: {len(colonne_consistenze)}")

    if campi_mancanti:
        avviso("Campi CRM senza una colonna CB corrispondente:")
        for campo in campi_mancanti:
            dettaglio(campo)

    if valori_non_riconosciuti:
        avviso("Commerciali non riconosciuti:")
        for valore in valori_non_riconosciuti:
            dettaglio(valore)

    return df


def pulisci_cb() -> Path:
    file_cb = trova_file_cb()
    df = pulisci_dataframe_cb(file_cb)

    archivia_file_correnti()
    return salva_file_correnti(file_cb, df)
