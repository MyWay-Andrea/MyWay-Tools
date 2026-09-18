from config import FILE_GADGET, COLONNE_DF
from genera_xlsx import genera_xlsx

import pandas as pd 
from colorama import Fore, init
init(autoreset=True)

def estrai_df(path_files):
    lista_df = []

    for negozio, path in path_files.items():
        df = pd.read_excel(path, dtype = str, engine = "openpyxl")
        df["NEGOZIO"] = negozio

        lista_df.append(df)

        print(Fore.GREEN + " ✓  " + Fore.RESET + f"{negozio}: lette {len(df)} righe")

    if not lista_df:
        print(Fore.RED + " ✕  Nessun file da aggregare")
        return pd.DataFrame()
    
    df_aggregato = pd.concat(lista_df, ignore_index = True)

    df_aggregato = df_aggregato[COLONNE_DF]
    print(f"\nTotale righe aggregate: {len(df_aggregato)}")

    return df_aggregato

def formatta_colonne(df:pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        nome_col = col.strip().lower()
        if "data" in nome_col:
            df[col] = pd.to_datetime(df[col], errors = "coerce")
        else:
            df[col] = df[col].astype(str)

    return df

def main(path_files):

    #estrai df dai path e aggrega in un unico df 
    df_aggregato = estrai_df(path_files)

    if df_aggregato.empty:
        return

    #formatta colonne 
    df_formattato = formatta_colonne(df_aggregato)

    percorso_output = genera_xlsx(df_formattato)
    print(Fore.GREEN + " ✓  " + Fore.RESET + f"File aggregato creato: {percorso_output}")

if __name__ == "__main__":
    main(FILE_GADGET)
