from io import BytesIO

import pandas as pd

from config import PATH_STORICO_BASI_DATI, carica_su_teams, trova_file


DATA_SPLIT_STORICO = pd.Timestamp("2026-06-01")


def formatta_colonne(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Atteso pandas.DataFrame, ricevuto {type(df).__name__}")
    df_formattato = df.copy()
    for colonna in df_formattato.columns:
        nome_colonna = colonna.strip().lower()
        if "data" in nome_colonna or "dalle" in nome_colonna or "inizio" in nome_colonna:
            df_formattato[colonna] = pd.to_datetime(df_formattato[colonna], errors="coerce")
    return df_formattato


def split_storico(df: pd.DataFrame) -> pd.DataFrame:
    df_formattato = df.copy()
    df_formattato["Data"] = pd.to_datetime(df_formattato["Data"], errors="coerce")
    return df_formattato[df_formattato["Data"] < DATA_SPLIT_STORICO]


def aggiorna_storico(df_appuntamenti: pd.DataFrame) -> pd.DataFrame:
    file_storico = trova_file(PATH_STORICO_BASI_DATI, "Storico")
    df_storico = pd.read_excel(
        BytesIO(file_storico["content"]), dtype=str, engine="openpyxl"
    )
    df_storico_precedente = split_storico(formatta_colonne(df_storico))
    df_storico_completo = pd.concat([df_storico_precedente, df_appuntamenti], ignore_index=True)

    if len(df_storico_completo) - len(df_appuntamenti) != len(df_storico_precedente):
        raise ValueError("Le lunghezze dei DataFrame non corrispondono durante l'aggregazione.")

    print("Caricamento Storico Appuntamenti...")
    carica_su_teams(df_storico_completo, PATH_STORICO_BASI_DATI)
    return df_storico_completo


def main() -> pd.DataFrame:
    from estrai_app_API import main as estrai_appuntamenti
    from formatta_appuntamenti import main as formatta_appuntamenti

    return aggiorna_storico(formatta_appuntamenti(estrai_appuntamenti()))


if __name__ == "__main__":
    main()
