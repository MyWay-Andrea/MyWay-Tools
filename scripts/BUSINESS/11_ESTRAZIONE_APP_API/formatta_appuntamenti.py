import pandas as pd

from config import (
    COLONNE_APPUNTAMENTI,
    CONVERSIONE_NOMI,
    PATH_BASI_DATI,
    PATH_PARQUET,
    carica_su_teams,
)


def converti_nomi_commerciali(serie: pd.Series, nomi: dict) -> pd.Series:
    if not isinstance(nomi, dict):
        raise TypeError(f"Atteso dizionario con nomi, ricevuto {type(nomi).__name__}")
    return serie.replace(nomi)


def main(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizza il DataFrame API mantenendo lo schema della cartella 07."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Atteso pandas.DataFrame, ricevuto {type(df).__name__}")

    colonne_mancanti = set(COLONNE_APPUNTAMENTI) - set(df.columns)
    colonne_extra = set(df.columns) - set(COLONNE_APPUNTAMENTI)
    if colonne_mancanti or colonne_extra:
        raise ValueError(
            "Le colonne non corrispondono con il formato appuntamenti. "
            f"Mancanti: {sorted(colonne_mancanti)}. Extra: {sorted(colonne_extra)}."
        )

    df_formattato = df.loc[:, COLONNE_APPUNTAMENTI].copy()
    df_formattato["Data"] = pd.to_datetime(df_formattato["Data"], errors="coerce")
    df_formattato["Orario"] = df_formattato["Data"].dt.strftime("%H:%M")
    df_formattato["In carico a"] = converti_nomi_commerciali(
        df_formattato["In carico a"], CONVERSIONE_NOMI
    )
    df_ordinato = df_formattato.sort_values(by="Data", ascending=False).reset_index(drop=True)

    print("Caricamento Appuntamenti...")
    carica_su_teams(df_ordinato, PATH_BASI_DATI, PATH_PARQUET)
    return df_ordinato
