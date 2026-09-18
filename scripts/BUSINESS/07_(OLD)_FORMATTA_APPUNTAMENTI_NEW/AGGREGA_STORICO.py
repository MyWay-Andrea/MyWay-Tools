import pandas as pd
import sys
from colorama import Fore, init
init(autoreset = True)

from config import (
    trova_file, carica_su_teams, carica_su_teams, elimina_file, 
    PATH_RAW_FILE, PATH_STORICO_BASI_DATI
)

from formatta_appuntamenti import main as importa_appuntamenti

def formatta_colonne(df):
    if not isinstance(df, pd.DataFrame):
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Il parametro passato alla funzione 'formatta_colonne' non è un pd.DataFrame")

    for col in df.columns:
        nome_col = col.strip().lower()

        if "data" in nome_col or "dalle" in nome_col or "inizio" in nome_col:
            df[col] = pd.to_datetime(df[col], errors = "coerce")

    return df

def split_storico(df):
    '''
    dato che non c'è una colonna che identifica ogni riga in modo univoco,
    splitto il df dalla data di inizio del nuovo CRM ed ogni giorno elimino i dati del nuovo CRM e 
    aggiungo tutti i giorni quella più aggiornata

    '''
    df["Data"] = pd.to_datetime(df["Data"])

    data_split = pd.to_datetime("2026-06-01")

    return df[df["Data"] < data_split]

def main(file_storico, file_appuntamenti):

    # 1. Importa df Appuntamenti già pronto
    df_appuntamenti = importa_appuntamenti(file_appuntamenti)

    print("Caricamento Storico Appuntamenti...")

    # 2. Importa df storico da lavorare 
    df_storico = pd.read_excel(
        file_storico,                   #file
        dtype = str,                    #formato dati import
        engine = "openpyxl"             #motore di elaborazione
    )
    
    # 3. Applica formati
    df_storico_formattato = formatta_colonne(df_storico)

    # 4. Split df storico
    df_split = split_storico(df_storico_formattato)

    # 5. Concatena appuntamenti a storico
    df_storico_completo = pd.concat([df_split, df_appuntamenti], ignore_index=True)

    if not (len(df_storico_completo) - len(df_appuntamenti)) == len(df_split):
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Le lunghezze dei df non corrispondono\n \
               - {len(df_storico_completo)} - storico VTIGER + TeamSystem)\n \
               - {len(df_appuntamenti)} - Appuntamenti CRM TeamSystem\n \
               - {len(df_storico_completo)} - {len(df_appuntamenti)} = {len(df_storico_completo) - len(df_appuntamenti)}\n \
               - quando dovrebbe essere {len(df_split)}.")

    # 6. Carica su teams
    carica_su_teams(df_storico_completo, PATH_STORICO_BASI_DATI)


if __name__ == "__main__":  

    file_storico = trova_file(PATH_STORICO_BASI_DATI, "Storico")
    file_appuntamenti = trova_file(PATH_RAW_FILE, "Appuntamenti")

    main(file_storico, file_appuntamenti)