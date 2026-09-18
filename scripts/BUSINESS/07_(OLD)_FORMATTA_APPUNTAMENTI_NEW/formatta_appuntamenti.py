import pandas as pd
import sys
from colorama import Fore, init
init(autoreset = True)


from config import (
    trova_file, carica_su_teams, elimina_file,
    PATH_RAW_FILE, PATH_BASI_DATI, PATH_PARQUET, COLONNE_APPUNTAMENTI, CONVERSIONE_NOMI
)

def add_customer(df):
    '''
    Aggiunge la colonna cliente perchè il CRM estra con 2 colonna: 1 lead se il cliente e lead e 1 azienda se è un anagrafica CB.
    Dato che ci sono anche appuntamenti su dei lead, estraggo tutte e due e poi aggrego dopo in una colonna unica
    '''
    if not isinstance(df, pd.DataFrame):
        print("[" + Fore.RED + "ERRORE" + Fore.RESET + "] il parametro passato alla funzione non è un dataframe")
        sys.exit(1)

    col_azienda = None
    col_lead = None

    for col in df.columns:
        nome_col = col.strip().lower()
        if "azienda" in nome_col:
            col_azienda = col
        elif "lead" in nome_col:
            col_lead = col

    if col_azienda is None and col_lead is None:
        print("[" + Fore.RED + "ERRORE" + Fore.RESET + "] nessuna colonna 'azienda' o 'lead' trovata")
        sys.exit(1)

    def scegli_cliente(row):
        if col_azienda and pd.notna(row[col_azienda]) and str(row[col_azienda]).strip() != "":
            return row[col_azienda]
        elif col_lead and pd.notna(row[col_lead]) and str(row[col_lead]).strip() != "":
            return row[col_lead]
        return None

    df["Cliente"] = df.apply(scegli_cliente, axis=1)
    
    return df

def correct_data(df, colonne):
    if not isinstance(df, pd.DataFrame):
        print("[" + Fore.RED + "ERRORE" + Fore.RESET + "] il parametro passato alla funzione non è un dataframe")
        sys.exit(1)

    col_data = None
    for col in df.columns:
        if "data" in col.strip().lower() or "orario" in col.strip().lower() or "dalle" in col.strip().lower() or "alle" in col.strip().lower():
            col_data = col
            break

    if col_data is None:
        print("[" + Fore.RED + "ERRORE" + Fore.RESET + "] nessuna colonna data trovata")
        sys.exit(1)

    df[col_data] = pd.to_datetime(df[col_data], errors="coerce")

    df["Data"] = pd.to_datetime(df[col_data], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df["Orario"] = df[col_data].dt.strftime("%H:%M")

    return df[colonne]

def converti_nomi_commerciali(serie: pd.Series, nomi: dict )-> pd.Series:
    '''
    Cicla tutta la colonna e sostituisce i valori in base al dizionario.
    La funzione "map" cerca il valore nella chiave del dizionario e 
    la sostituisce con il valore 
    '''
    if not isinstance(nomi, dict):
        raise TypeError(
            f"Atteso dizionario con nomi, ricevuto {type(nomi).__name__}"
        )
    
    return serie.replace(nomi)
    

def main(file):

    print("Caricamento Appuntamenti...")
    # 1. importa file appuntamenti
    df = pd.read_excel(file, dtype = str, engine = "openpyxl")

    # 2. aggiungi colonna cliente
    df_cliente = add_customer(df)

    # 3. correggi data 
    df_data = correct_data(df_cliente, COLONNE_APPUNTAMENTI)


    # 4. ordina per data
    df_ordinato = df_data.sort_values(by="Data", ascending=False).reset_index(drop=True)

    # 5. converti nomi
    df_ordinato['In carico a'] = converti_nomi_commerciali(df_ordinato['In carico a'], CONVERSIONE_NOMI)

    # 6. carica su teams
    carica_su_teams(df_ordinato, PATH_BASI_DATI, PATH_PARQUET)
    
    # 7. elimina file da "00_RAW_FILE"
    elimina_file(file)

    return df_ordinato
    
if __name__ == "__main__":
    file_appuntamenti = trova_file(PATH_RAW_FILE, "Appuntamenti")
    main(file_appuntamenti)