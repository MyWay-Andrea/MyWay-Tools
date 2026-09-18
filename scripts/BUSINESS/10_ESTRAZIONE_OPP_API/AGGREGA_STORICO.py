from io import BytesIO

import pandas as pd
from colorama import Fore, init

from config import PATH_STORICO_BASI_DATI, carica_su_teams, trova_file

init(autoreset=True)


def formatta_dati(df: pd.DataFrame) -> pd.DataFrame:
    try:
        for colonna in df.columns:
            nome_colonna = colonna.strip().lower()
            if "iva" in nome_colonna:
                df[colonna] = df[colonna].astype(str).str.zfill(11)
            if "data" in nome_colonna:
                df[colonna] = pd.to_datetime(df[colonna], errors="coerce").dt.normalize()
            if "quantit" in nome_colonna or "qtà" in nome_colonna:
                df[colonna] = df[colonna].fillna(50).astype(int)
            if "prezzo" in nome_colonna or "importo" in nome_colonna:
                df[colonna] = pd.to_numeric(df[colonna], errors="coerce")
    except Exception as errore:
        print(f"[{Fore.RED}ERRORE{Fore.RESET}] Errore durante la formattazione dello storico --> {errore}")
        raise

    return df


def aggiorna_storico(df_opportunita: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df_opportunita, pd.DataFrame):
        raise TypeError(f"Atteso pandas.DataFrame, ricevuto {type(df_opportunita).__name__}")

    file_storico = trova_file(PATH_STORICO_BASI_DATI, "Storico")
    df_storico = pd.read_excel(
        BytesIO(file_storico["content"]), dtype=str, engine="openpyxl"
    )
    df_storico = formatta_dati(df_storico)

    df_vtiger = df_storico[
        df_storico["Codice Opportunità"].astype(str).str.startswith("QUO")
    ]
    df_storico_completo = pd.concat([df_vtiger, df_opportunita], ignore_index=True)

    if len(df_storico_completo) - len(df_opportunita) != len(df_vtiger):
        raise ValueError("Le lunghezze dei DataFrame non corrispondono durante l'aggregazione.")

    print("Caricamento Storico opportunità...")
    carica_su_teams(df_storico_completo, PATH_STORICO_BASI_DATI)
    return df_storico_completo


def main():
    from estrai_opp_API import main as estrai_opportunita
    from formatta_opportunita import main as formatta_opportunita

    return aggiorna_storico(formatta_opportunita(estrai_opportunita()))


if __name__ == "__main__":
    main()
