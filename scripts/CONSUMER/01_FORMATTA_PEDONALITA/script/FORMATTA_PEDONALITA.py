import pandas as pd
from io import BytesIO
from colorama import Fore, init, Style
import re
from prepara_pedonalita import main as prepara_file_da_aggregare, seleziona_colonne
from config import (
    trova_database_pedonalita,
    salva_database_pedonalita,
    elimina_raw_pedonalita,
    COLONNE_ORDINATE,
)
init(autoreset = True)

#PRIMA DI CONCATENARE I DATI CONTROLLA LA CONFORMITA DEI DUE DATAFRAME 
def verifica_conformità(df_1, df_2):
    colonne_1 = df_1.columns.to_list()
    colonne_2 = df_2.columns.to_list()
    if colonne_1 == colonne_2:
        return True
    else:
        return False

#AGGREGA I 2 DATAFRAME ACCODANDO I DATI AL DB
#-------------------------------------------------------------
def aggrega_df(df_1, df_2):
    df_agg = pd.concat([df_1, df_2],  
                       ignore_index = True)
    len_prima = len(df_1)
    df_agg = df_agg.drop_duplicates(subset = ["Negozio", "Data", "Ora"], keep = "last")
    len_dopo = len(df_agg)
    nuovi_record = len_dopo - len_prima
    
    return df_agg, nuovi_record

#CARICA O ELIMINA FILE E POI CARICA
#------------------------------------------------------------
#FLUSSO PRINCIPALE 
#-------------------------------------------------------------
def main(file_db, df_ped_lav):

    df_ped_DB = pd.read_parquet(BytesIO(file_db["content"]))
    df_ped_DB["Data"] = pd.to_datetime(df_ped_DB["Data"])
    
    if not "Giorno_num" in df_ped_DB.columns:
        mappa_giorni = {
            0: "Lunedì",
            1: "Martedì", 
            2: "Mercoledì",
            3: "Giovedì",
            4: "Venerdì",
            5: "Sabato",
            6: "Domenica"
        }

        df_ped_DB["Giorno_num"]  = df_ped_DB["Data"].dt.dayofweek         
        df_ped_DB["Giorno_nome"] = df_ped_DB["Giorno_num"].map(mappa_giorni) 
        df_ped_DB = seleziona_colonne(df_ped_DB, COLONNE_ORDINATE)

    df_ped_lav["Data"] = pd.to_datetime(df_ped_lav["Data"])

    if verifica_conformità(df_ped_DB,df_ped_lav):
        #aggrega e riuove i duplicati
        df_db, nuovi_record = aggrega_df(df_ped_DB, df_ped_lav)
    else:
        print(Fore.RED + "[PEDONALITA] ❌ ERRORE, i 2 df non combaciano")
        exit()

    #ordina per negozio, data, ora
    df_db = df_db.sort_values(by = ["Data", "Negozio", "Ora"])
    ultimo_giorno = df_db["Data"].iloc[-1].strftime("%d-%m-%Y")
    
    
    salva_database_pedonalita(df_db, ultimo_giorno)
    
    
    print("\nSono stati caricati " + Fore.LIGHTBLUE_EX + f"{nuovi_record}" + Fore.RESET + " nuovi record....")
    print(Fore.GREEN +  " ✅ Caricamento avvenuto con " + Fore.GREEN + Style.BRIGHT + "SUCCESSO")
    print(df_db)


if __name__ == "__main__":
    try:
        df_ped_lav, file_raw = prepara_file_da_aggregare()
        
    except Exception as e:
        print(Fore.RED + f"[PEDONALITA] ❌ ERRORE nell'importazione del df lavorato... {e}")
        raise
    
    print("Ricerca database Pedonalita su SharePoint...")
    file_db = trova_database_pedonalita()

    '''
    se non esiste il file all'interno della cartella su Teams, prende
    il file df_ped_lav e lo carica come se fosse quello definitivo 
    '''

    if file_db is None:
        ultimo_giorno = pd.to_datetime(df_ped_lav["Data"]).max().strftime("%d-%m-%Y")
        salva_database_pedonalita(df_ped_lav, ultimo_giorno)
    else:
        main(file_db, df_ped_lav)
    
    # Elimina il file raw dopo aver estratto i dati
    try:
        elimina_raw_pedonalita(file_raw)
    except Exception as e:
        print(Fore.RED + f"⚠️ Errore nell'eliminazione del file raw: {e}")
