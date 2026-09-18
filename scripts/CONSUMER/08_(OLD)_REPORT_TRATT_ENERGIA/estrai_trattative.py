import pandas as pd
from colorama import Fore, init
init(autoreset=True)

from config import COLONNE_TRACCIAMENTO

def estrai_dati_file(percorsi) -> list[pd.DataFrame]:
    lista_df = []

    for path in percorsi:
        nome_negozio = path.name.split("-")[0]

        df = pd.read_excel(path, engine="openpyxl")

        df["NEGOZIO"] = nome_negozio
        lista_df.append(df)

        print(Fore.GREEN + " ✓  " + Fore.RESET + f"{nome_negozio}") 

    return lista_df

def formatta_date(lista_df: list[pd.DataFrame]) -> list[pd.DataFrame]:
    for df in lista_df:
        for col in df.columns:
            if "data" in col.lower():
                df[col] = pd.to_datetime(df[col], errors="coerce")

    return lista_df

def main(files):
    dataframes = formatta_date(estrai_dati_file(files))
    dataframes = [df[COLONNE_TRACCIAMENTO] for df in dataframes]

    return pd.concat(dataframes, ignore_index=True)
