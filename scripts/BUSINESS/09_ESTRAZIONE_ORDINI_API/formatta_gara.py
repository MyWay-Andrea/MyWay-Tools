from config import (
    trova_file, carica_su_teams, 
    COLONNE_CORRETTE_GARA, COLONNE_OUTPUT_GARA, PATH_BASI_DATI, PATH_PARQUET)

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
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors = "coerce")

            #formatta p.iva
            if nome_col == "partita iva":
                df[col] = df[col].astype(str).str.zfill(11)

            #formatta qtà e scala sconti
            if "quantit" in nome_col or "qtà" in nome_col or "sconto" in nome_col:
                df[col] = pd.to_numeric(df[col], errors = "coerce").fillna(0).astype(int)

            #formatta il prezzo 
            if "prezzo" in nome_col:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            
            if "stato" in nome_col:
                for i in df.index:
                    if df.loc[i, col] == "Parzialmente evaso":
                        if pd.isna(df.loc[i, "Data Inserimento OmniSales"]) and pd.isna(df.loc[i, "ID Pratica"]) and pd.isna(df.loc[i, "Data Attivazione"]):
                            df.loc[i, col] = "Da Inserire"
                        elif not pd.isna(df.loc[i, "Data Inserimento OmniSales"]) and not pd.isna(df.loc[i, "ID Pratica"]) and not pd.isna(df.loc[i, "Data Attivazione"]):
                            df.loc[i,col] = "Attivato"
                        else:
                            df.loc[i, col] = "In Attivazione"

                    elif df.loc[i, col] == "annullato":
                        df.loc[i,col] = "Annullato"
                    
                    elif df.loc[i, col] == "evaso":
                        df.loc[i, col] = "Attivato"

        #APPLICA NOME CORRETTO ALLE COLONNE
        if len(df.columns) != len(COLONNE_CORRETTE_GARA):
            raise ValueError(
                f"Il file ha {len(df.columns)} colonne, attese {len(COLONNE_CORRETTE_GARA)}"
        )

        df.columns = COLONNE_CORRETTE_GARA

    except Exception as e:
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Errore durante la formattazione del df --> {e}")
        raise

    
    return df
        
def main(df):

    print("\nCaricamento Gara (Inflow)....")

    # 1. Formatta colonne
    df_formattato = formatta_colonne(df)

    # 2. Carica su Teams

    df_output = df_formattato[COLONNE_OUTPUT_GARA]
    carica_su_teams(df_output, PATH_BASI_DATI, PATH_PARQUET)
    
    return df_formattato
