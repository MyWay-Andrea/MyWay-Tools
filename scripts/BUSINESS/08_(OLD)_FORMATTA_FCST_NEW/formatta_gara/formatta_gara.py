import sys
from pathlib import Path
import pandas as pd 
from colorama import Fore, Style, init
init(autoreset=True)

# Aggiunge la cartella padre (08_FORMATTA_FCST_NEW) al path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import (
    carica_su_teams, elimina_file,
    COLONNE_CORRETTE_GARA, CONVERSIONE_NOMI, PATH_BASI_DATI, PATH_PARQUET)

def _converti_nomi_commerciali(serie:pd.Series, nomi:dict) -> pd.DataFrame:
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

def formatta_colonne(df:pd.DataFrame) -> pd.DataFrame:
    try:
        #FORMATTA TUTTE LE COLONNE NEL FORAMTO CORRETTO
        for col in df.columns:
            nome_col = col.strip().lower()

            #formatta colonne data
            if "data" in nome_col:
                df[col] = pd.to_datetime(df[col], errors = "coerce").dt.date

            #formatta p.iva
            if nome_col == "partita iva":
                df[col] = df[col].astype(str).str.zfill(11)

            #formatta qtà e scala sconti
            if "quantit" in nome_col or "qtà" in nome_col or "sconto" in nome_col:
                df[col] = pd.to_numeric(df[col], errors = "coerce").fillna(0).astype(int)

            #formatta il prezzo 
            if "prezzo" in nome_col:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            #formatta l'agente 
            if "commerciale" in nome_col:
                df[col] = _converti_nomi_commerciali(df[col], CONVERSIONE_NOMI)
            
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

        #APPLICA NOME CORRETTO ALLE COLONNE
        if len(df.columns) != len(COLONNE_CORRETTE_GARA):
            raise ValueError(
                f"Il file ha {len(df.columns)} colonne, attese {len(COLONNE_CORRETTE_GARA)}"
        )

        df.columns = COLONNE_CORRETTE_GARA

    except Exception as e:
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Errore durante la formattazione del df --> {e}")
        sys.exit(1)
    
    return df
        
def main(file):

    print("\nCaricamento Gara (Inflow)....")
    # 1. Importa file "Gara_inflow"
    df = pd.read_excel(file, dtype = str, engine='openpyxl')

    # 2. Formatta colonne
    df_formattato = formatta_colonne(df)

    # 3. Carica su Teams
    carica_su_teams(df_formattato, "Gara (Inflow)", PATH_BASI_DATI, PATH_PARQUET)

    # 4. Elimina file da "00_RAW_FILE"
    elimina_file(file)
    
    return df_formattato

