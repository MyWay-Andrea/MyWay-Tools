from config import (
    trova_file, carica_su_teams,
    PATH_RAW_FILE, COLONNE_CORRETTE_STORICO, PATH_STORICO_BASI_DATI, PATH_STORICO_PARQUET, PATH_STORICO_BASI_DATI
    )

from formatta_gara import main as importa_gara

import pandas as pd
from pathlib import Path
from colorama import Fore, Style, init
init(autoreset=True)
import sys

def formatta_colonne(df:pd.DataFrame) -> pd.DataFrame:
    try:
        #FORMATTA TUTTE LE COLONNE NEL FORAMTO CORRETTO
        for col in df.columns:
            nome_col = col.strip().lower()

            #formatta colonne data
            if "data" in nome_col:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

            #formatta p.iva
            if nome_col == "partita iva":
                df[col] = df[col].astype(str).str.zfill(11)

            #formatta qtà e scala sconti
            if "quantit" in nome_col or "qtà" in nome_col or "sconto" in nome_col:
                df[col] = pd.to_numeric(df[col], errors = "coerce").fillna(0).astype(int)

            #formatta il prezzo 
            if "prezzo" in nome_col:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            
            #formatta l'importo
            if "importo" in nome_col:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            if "stato" in nome_col:
                for i in df.index:
                    if df.loc[i, col] == "Campo non valorizzato":
                        if pd.isna(df.loc[i, "Data Inserimento OmniSales"]) and pd.isna(df.loc[i, "ID Pratica"]):
                            df.loc[i, col] = "Da Inserire"
                        else:
                            df.loc[i, col] = "In Attivazione"

                    elif df.loc[i, col] == "annullato":
                        df.loc[i,col] = "Annullato"
                    
                    elif df.loc[i, col] == "evaso":
                        df.loc[i, col] = "Attivato"

    except Exception as e:
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Errore durante la formattazione del df --> {e}")
        print(list(df.columns))
    
    return df

def _check_chiavi(df, chiavi):
    for valore in chiavi:
        df[valore] = df[valore].astype(str)
    
    return df

def upsert_file(df_storico, df_gara):
    '''
    Funzone che fa upsert dei due file, ovvero, carica il file gara completamente
    e successivamente rimuove i duplicati mantenendo gli ultimi aggiunti. Questo fa si che 
    gli ultimi dati (specialmente la gara) sia sempre aggiornata correttamente.
    Filtro il df_storico dalla data della gara di ingresso del nuovo CRM (01/04/2026) in modo tale da tenere
    aggiornati i dati nuovi ma non cancellari i duplicati dei vecchi ordini, perchè presenti.
    '''
    chiavi = ["ID Pratica", "Prodotto esistente"]

    df_storico  = _check_chiavi(df_storico, chiavi)
    df_gara     = _check_chiavi(df_gara, chiavi)
    
    df_storico["Data Attivazione"] = pd.to_datetime(
        df_storico["Data Attivazione"],
        dayfirst=True,
        errors="coerce"
    )
    
    #split dati ad inizio gara apr-giu
    data_taglio = pd.Timestamp("2026-04-01")

    # storico precedente al nuovo CRM
    df_vecchio = df_storico[
        df_storico["Data Attivazione"] < data_taglio
    ]

    # dati CRM da aggiornare
    df_mwr = df_storico[
        df_storico["Data Attivazione"] >= data_taglio
    ]

    # upsert
    df_mwr_aggiornato = (
        pd.concat([df_mwr, df_gara], ignore_index=True)
        .drop_duplicates(
            subset=chiavi,
            keep="last"
        )
    )

    # ricostruzione storico
    df_storico_aggiornato = pd.concat(
        [df_vecchio, df_mwr_aggiornato],
        ignore_index=True
    )

    return df_storico_aggiornato

def main(file_gara, file_storico):
    '''
    Prende il file "Gara (Inflow)" precedentemente formattato e lo concatena al 
    file storico leggednolo dalla cartelal ".parquet" in modo tale da non aver 
    problemi con i formati delle colonne
    '''

    print("Caricamento Storico Gara...")

    # 1. Importiamo df gara precedentemente formattato
    df_gara = importa_gara(file_gara)

    # 2. Organizziamo colonne per storico
    df_gara = df_gara[COLONNE_CORRETTE_STORICO]
    
    # 3. Improtiamo df storico
    df_storico = pd.read_excel(file_storico, dtype = str)
    
    
    # 4. Formatta colonne df storico
    df_storico = formatta_colonne(df_storico)
    
    # 4. Check che abbiano le stesse colonne
    if not list(df_gara.columns) == list(df_storico.columns):
        print(df_gara.columns)
        print(df_storico.columns)
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] i 2 df non hanno le stesse colonne")
        sys.exit(1)

    
    # 5. Aggrega per creare db storico
    df_aggregato = upsert_file(df_storico, df_gara)
    
    # 6. Carica su Teams il file completo
    carica_su_teams(df_aggregato, PATH_STORICO_BASI_DATI)

if __name__ == "__main__":

    #Importa i 2 file e passali alla funzione main
    file_gara = trova_file(PATH_RAW_FILE, "Gara")
    file_storico = trova_file(PATH_STORICO_BASI_DATI, "Storico")
    main(file_gara, file_storico)