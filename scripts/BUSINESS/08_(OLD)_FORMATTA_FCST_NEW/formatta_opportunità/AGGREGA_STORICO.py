import pandas as pd
import sys
from pathlib import Path
from colorama import Fore, init
init(autoreset = True)

# Aggiunge la cartella padre (08_FORMATTA_FCST_NEW) al path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import (
    trova_file, carica_su_teams,
    PATH_RAW_FILE, PATH_STORICO_BASI_DATI
)

from formatta_opportunità.formatta_opportunita import main as importa_opportunita

def formatta_dati(df):
    try:
        for col in df.columns:
            nome_col = col.strip().lower()
            
            #formatta partita iva 
            if "iva" in nome_col:
                df[col] = df[col].astype(str).str.zfill(11)
            
            #formatta date
            if "data" in nome_col:
                df[col] = pd.to_datetime(df[col],  errors = "coerce").dt.normalize()
            
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

    except Exception as e:
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Errore durante la formattazione del df --> {e}")
        sys.exit(1)

    return df


def main(file_opp, file_storico):

    
    # 1. Importa df opportunità
    df_opportunita = importa_opportunita(file_opp)

    print("Caricamento Storico opportunità...")

    # 2. Importa df storico_opportunita
    df_storico = pd.read_excel(file_storico, dtype = str, engine = "openpyxl")

    # 3. Formatta colonne "storico_opportunita"
    df_stor_formattato = formatta_dati(df_storico)

    # 4. split dati vecchi da colonna "Codice Opportunità"
    df_split = df_stor_formattato[
        df_stor_formattato["Codice Opportunità"].astype(str).str.startswith("QUO")
    ]
    
    # 5. Concatena i due df
    df_storico_completo = pd.concat([df_split, df_opportunita], ignore_index=True)

    if not (len(df_storico_completo) - len(df_opportunita)) == len(df_split):
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Le lunghezze dei df non corrispondono\n \
               - {len(df_storico_completo)} - storico VTIGER)\n \
               - {len(df_opportunita)} - opportunità CRM TeamSystem\n \
               - {len(df_storico_completo)} - {len(df_opportunita)} = {len(df_storico_completo) - len(df_opportunita)}\n \
               - quando dovrebbe essere {len(df_split)}.")
    
    # 6. Carica su teams
    carica_su_teams(df_storico_completo, "Storico Opportunita", PATH_STORICO_BASI_DATI)