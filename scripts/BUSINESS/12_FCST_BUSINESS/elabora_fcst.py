from pathlib import Path
import pandas as pd
from datetime import datetime
from colorama import Fore, init
init(autoreset = True)

from config import (
    trova_file,
    PATH_ONEDRIVE_FILE
)

def estrai_df(file: Path, ext: str) -> pd.DataFrame:
    if ext in ["xls", "xlsx"]:
        df = pd.read_excel(file, dtype=str)
    elif ext == "parquet":
        df = pd.read_parquet(file)
    elif ext == "csv":
        df = pd.read_csv(file, dtype=str)
    else:
        raise ValueError("[" + Fore.RED + "ERRORE" + Fore.RESET + f"] Estensione '{ext}' non supportata: ")
    
    print(Fore.GREEN + "✓ " + Fore.RESET + f"df {file.name}")
    return df

def _leggi_estensione_file(file:Path) -> tuple[Path, str]:
    return file, file.name.split(".")[1]

def formatta_df(df:pd.DataFrame) -> pd.DataFrame:

    df.columns = df.columns.str.strip().str.lower()

    for col in df.columns:

        if "data" in col:
            df[col] = pd.to_datetime(df[col], errors = "coerce").dt.normalize()

        if "quantità" in col or "prezzo" in col or "importo" in col:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

def main(f_g, f_o, f_a):

    # 1. Leggi df   --> * prima della funzioane spacchetta la tupla restituita da "_leggi_estensione_file"
    print("\n === Estraione df === ")
    df_gara = estrai_df(*_leggi_estensione_file(f_g))
    df_oppo = estrai_df(*_leggi_estensione_file(f_o))
    df_appu = estrai_df(*_leggi_estensione_file(f_a))

    # 2. Formatta df
    print("\n === Formattazione df ===")
    df_gara_formattato = formatta_df(df_gara)
    df_oppo_formattato = formatta_df(df_oppo)
    df_appu_formattato = formatta_df(df_appu)
    print(Fore.GREEN + "✓ " + Fore.RESET + f"df formattati corretamente")

    return df_gara_formattato, df_oppo_formattato, df_appu_formattato

if __name__ == "__main__":

    # 1. importa file 
    print("\n === Ricerca file per file FCST ===")
    file_gara = trova_file(PATH_ONEDRIVE_FILE, "gara")
    file_opportunita = trova_file(PATH_ONEDRIVE_FILE, "opportunita")
    file_appuntamenti = trova_file(PATH_ONEDRIVE_FILE, "appuntamenti")

    
    # 2. chiama funzione 
    main(file_gara, file_opportunita, file_appuntamenti)