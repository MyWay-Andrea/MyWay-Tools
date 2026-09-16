import pandas as pd
from colorama import Fore, init

from config import (
    COLONNE_OPPORTUNITA,
    CONVERSIONE_NOMI,
    PATH_BASI_DATI,
    PATH_PARQUET,
    carica_su_teams,
)

init(autoreset=True)


def _converti_nomi_commerciali(serie: pd.Series, nomi: dict) -> pd.Series:
    if not isinstance(nomi, dict):
        raise TypeError(f"Atteso dizionario con nomi, ricevuto {type(nomi).__name__}")
    return serie.replace(nomi)


def formatta_dati(df: pd.DataFrame, conv_nomi: dict) -> pd.DataFrame:
    try:
        for colonna in df.columns:
            nome_colonna = colonna.strip().lower()

            if "iva" in nome_colonna:
                df[colonna] = df[colonna].astype(str).str.zfill(11)
            if "data" in nome_colonna:
                df[colonna] = pd.to_datetime(
                    df[colonna], dayfirst=True, errors="coerce"
                ).dt.normalize()
            if "quantit" in nome_colonna or "qtà" in nome_colonna:
                df[colonna] = df[colonna].fillna(50).astype(int)
            if "prezzo" in nome_colonna or "importo" in nome_colonna:
                df[colonna] = pd.to_numeric(df[colonna], errors="coerce")
            if "proprietario" in nome_colonna:
                df[colonna] = _converti_nomi_commerciali(df[colonna], conv_nomi)
    except Exception as errore:
        print(f"[{Fore.RED}ERRORE{Fore.RESET}] Errore durante la formattazione del df --> {errore}")
        raise

    return df


def main(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Atteso pandas.DataFrame, ricevuto {type(df).__name__}")

    colonne_mancanti = set(COLONNE_OPPORTUNITA) - set(df.columns)
    colonne_extra = set(df.columns) - set(COLONNE_OPPORTUNITA)
    if colonne_mancanti or colonne_extra:
        raise ValueError(
            "Le colonne non corrispondono con il formato proposto. "
            f"Mancanti: {sorted(colonne_mancanti)}. Extra: {sorted(colonne_extra)}."
        )

    df_formattato = formatta_dati(df.loc[:, COLONNE_OPPORTUNITA].copy(), CONVERSIONE_NOMI)
    df_aperta = df_formattato[
        df_formattato["Stato (Opportunità)"] == "Aperta"
    ]

    print("\nCaricamento Opportunità...")
    carica_su_teams(df_aperta, PATH_BASI_DATI, PATH_PARQUET)
    return df_formattato
