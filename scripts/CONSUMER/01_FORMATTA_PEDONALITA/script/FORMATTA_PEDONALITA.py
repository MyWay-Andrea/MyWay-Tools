import pandas as pd
from colorama import Fore, init, Style
import re
from prepara_pedonalita import main as prepara_file_da_aggregare, seleziona_colonne
from config import PATH_DATABASE, PATH_RAW_FOLDER, trova_file, salva_su_teams_excel, elimina_file_da_cartella, COLONNE_ORDINATE, PATH_TEAM_CONSUMER
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
def carica_elimina_teams(path_basi_dati , path_consumer, path_parquet, df, ultimo_giorno):
    '''
    elimina file vecchi e carica file in 3 cartelle differenti:
    '''
    path_basi_dati_folder = path_basi_dati.parent
    path_consumer_folder = path_consumer.parent
    path_parquet_folder = path_parquet.parent
    elimina_file_da_cartella(path_basi_dati_folder, path_consumer_folder, path_parquet_folder, ultimo_giorno)

    #salva parquet in /00_SCAMBIO_DOCUMENTI/.parquet
    df.to_parquet(path_parquet)

    #salva il /00_SCAMBIO_SOCUMENTI/BASI_DATI_xlsx
    salva_su_teams_excel(path_basi_dati, df)

    #salva in /TEAM CONSUMER/_
    salva_su_teams_excel(path_consumer, df)
        

#FLUSSO PRINCIPALE 
#-------------------------------------------------------------
def main(path_db, df_ped_lav):

    df_ped_DB = pd.read_parquet(path_db)
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
    
    
    #salva il DB su TEAMS e rimuovi quello vecchio
    filename_scambio_documenti = PATH_DATABASE.parent / "BASI_DATI_xlsx" / f"Pedonalità_{ultimo_giorno}.xlsx"
    filename_team_consumer = PATH_TEAM_CONSUMER / f"Pedonalità_{ultimo_giorno}.xlsx"
    filename_parquet = PATH_DATABASE / f"Pedonalità_{ultimo_giorno}.parquet"
    #carica su scambio documenti
    carica_elimina_teams(filename_scambio_documenti, filename_team_consumer, filename_parquet, df_db, ultimo_giorno)
    
    
    print("\nSono stati caricati " + Fore.LIGHTBLUE_EX + f"{nuovi_record}" + Fore.RESET + " nuovi record....")
    print(Fore.GREEN +  " ✅ Caricamento avvenuto con " + Fore.GREEN + Style.BRIGHT + "SUCCESSO")
    print(df_db)


if __name__ == "__main__":
    try:
        df_ped_lav, path_raw_file = prepara_file_da_aggregare(PATH_RAW_FOLDER)
        
    except Exception as e:
        print(Fore.RED + f"[PEDONALITA] ❌ ERRORE nell'importazione del df lavorato... {e}")
    
    print("Ricerca FIle in Teams...")
    
    path_DB, vuoto = trova_file(PATH_DATABASE)

    '''
    se non esiste il file all'interno della cartella su Teams, prende
    il file df_ped_lav e lo carica come se fosse quello definitivo 
    '''

    if path_DB is None and df_ped_lav:
        filename_parquet = PATH_DATABASE / f"Pedonalità.parquet"
        df_ped_lav.to_parquet(filename_parquet)
    else:
        main(path_DB, df_ped_lav)
    
    # Elimina il file raw dopo aver estratto i dati
    try:
        if path_raw_file.exists():
            path_raw_file.unlink()
            print(Fore.GREEN + f"✅ File raw eliminato: {path_raw_file.name}")
    except Exception as e:
        print(Fore.RED + f"⚠️ Errore nell'eliminazione del file raw: {e}")