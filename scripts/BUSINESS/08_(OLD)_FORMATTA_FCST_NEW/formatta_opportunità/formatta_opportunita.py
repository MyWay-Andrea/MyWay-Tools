import pandas as pd
from colorama import Fore, init
init(autoreset = True)
import sys
from pathlib import Path

# Aggiunge la cartella padre (08_FORMATTA_FCST_NEW) al path
sys.path.append(str(Path(__file__).resolve().parent.parent))
                
from config import (
    carica_su_teams, elimina_file,
    PATH_BASI_DATI, PATH_PARQUET, COLONNE_OPPORTUNITA, CONVERSIONE_NOMI

)

def _converti_nomi_commerciali(serie: pd.Series, nomi: dict )-> pd.Series:
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
    
def formatta_dati(df, conv_nomi):
    try:
        for col in df.columns:
            nome_col = col.strip().lower()
            
            #formatta partita iva 
            if "iva" in nome_col:
                df[col] = df[col].astype(str).str.zfill(11)
            
            #formatta date
            if "data" in nome_col:
                df[col] = pd.to_datetime(df[col], dayfirst = True, errors = "coerce").dt.normalize()
            
            #formatta Qtà
            if "quantit" in nome_col or "qtà" in nome_col:
                df[col] = (
                    df[col]
                    .fillna(50)
                    .astype(int)
                )

            #formatta valute
            if "prezzo" in nome_col or "importo" in nome_col:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            #conversione nomi
            if "proprietario" in nome_col:
                df[col] = _converti_nomi_commerciali(df[col], conv_nomi)
    except Exception as e:
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Errore durante la formattazione del df --> {e}")
    return df

def main(file_path):

     # 1. importa dati
    df = pd.read_csv(file_path)

    # 2. applica colonne
    if not len(df.columns) == len(COLONNE_OPPORTUNITA):
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Le colonne non corrispondono con il formato proposto")
        sys.exit(1)

    df.columns = COLONNE_OPPORTUNITA

    # 3. applica formati
    df_formattato = formatta_dati(df, CONVERSIONE_NOMI)
    
    # 5. Filtriamo solo stato = "Aperta"
    df_aperta = df_formattato[df_formattato["Stato (Opportunità)"] == "Aperta"]

    # 6. salva su teams
    print("\nCaricamento Opportunità...")
    carica_su_teams(df_aperta, "opportunita", PATH_BASI_DATI, PATH_PARQUET)

    # 7. elimina file da "00_RAW_FILE"
    elimina_file(file_path)
    
    return df_formattato

