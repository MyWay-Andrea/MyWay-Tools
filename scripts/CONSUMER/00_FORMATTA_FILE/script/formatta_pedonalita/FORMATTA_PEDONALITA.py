import pandas as pd
from colorama import Fore, init, Style
from formatta_pedonalita.prepara_pedonalita import main as prepara_file_da_aggregare, seleziona_colonne
from formatta_pedonalita.config import (
    PATH_DATABASE,
    PATH_RAW_FOLDER,
    trova_file,
    salva_su_teams_parquet,
    salva_su_teams_excel,
    elimina_file_da_cartella,
    COLONNE_ORDINATE,
)

init(autoreset=True)


# PRIMA DI CONCATENARE I DATI CONTROLLA LA CONFORMITA DEI DUE DATAFRAME
def verifica_conformità(df_1, df_2):
    colonne_1 = df_1.columns.to_list()
    colonne_2 = df_2.columns.to_list()
    if colonne_1 == colonne_2:
        return True
    else:
        print(Fore.YELLOW + f"[DEBUG] Colonne DB:  {colonne_1}")
        print(Fore.YELLOW + f"[DEBUG] Colonne LAV: {colonne_2}")
        return False


# AGGREGA I 2 DATAFRAME ACCODANDO I DATI AL DB
def aggrega_df(df_1, df_2):
    df_agg = pd.concat([df_1, df_2], ignore_index=True)
    len_prima = len(df_1)
    df_agg = df_agg.drop_duplicates(subset=["Negozio", "Data", "Ora"], keep="last")
    len_dopo = len(df_agg)
    nuovi_record = len_dopo - len_prima
    return df_agg, nuovi_record


# CARICA O ELIMINA FILE E POI CARICA
def carica_elimina_teams(path_folder, df, path_file, ultimo_giorno):
    elimina_file_da_cartella(path_folder, ultimo_giorno)
    salva_su_teams_parquet(path_folder, df, ultimo_giorno)
    salva_su_teams_excel(path_folder, df, ultimo_giorno)


# FLUSSO PRINCIPALE — contiene tutta la logica, importabile e eseguibile direttamente
def main(path_raw_file):
    # 1. Prepara il file raw e ottieni df e path
    try:
        df_ped_lav = prepara_file_da_aggregare(path_raw_file)
    except Exception as e:
        print(Fore.RED + f"[PEDONALITA] ❌ ERRORE nell'importazione del df lavorato... {e}")
        return False

    # 2. Cerca il DB su Teams
    print("Ricerca file in Teams...")
    path_DB, vuoto = trova_file(PATH_DATABASE)

    # 3. Se non esiste il DB, carica il file lavorato come primo DB
    if path_DB is None:
        salva_su_teams_parquet(PATH_DATABASE, df_ped_lav)
        print(Fore.GREEN + "✅ Primo caricamento DB completato.")
    else:
        # 4. Carica il DB esistente
        df_ped_DB = pd.read_parquet(path_DB)

        # Aggiunge colonne giorno se mancanti (retrocompatibilità)
        if "Giorno_num" not in df_ped_DB.columns:
            mappa_giorni = {
                0: "Lunedì",
                1: "Martedì",
                2: "Mercoledì",
                3: "Giovedì",
                4: "Venerdì",
                5: "Sabato",
                6: "Domenica",
            }
            df_ped_DB["Giorno_num"] = df_ped_DB["Data"].dt.dayofweek
            df_ped_DB["Giorno_nome"] = df_ped_DB["Giorno_num"].map(mappa_giorni)
            df_ped_DB = seleziona_colonne(df_ped_DB, COLONNE_ORDINATE)

        if not verifica_conformità(df_ped_DB, df_ped_lav):
            print(Fore.RED + "[PEDONALITA] ❌ ERRORE, i 2 df non combaciano")
            return False

        # 5. Aggrega e rimuove duplicati
        df_db, nuovi_record = aggrega_df(df_ped_DB, df_ped_lav)

        # 6. Ordina per data, negozio, ora
        df_db = df_db.sort_values(by=["Data", "Negozio", "Ora"])
        ultimo_giorno = df_db["Data"].iloc[-1].strftime("%d-%m-%Y")
        df_db.loc[:, "Data"] = (
            pd.to_datetime(df_db.loc[:, "Data"], dayfirst=True).dt.strftime("%d/%m/%Y")
        )

        # 7. Salva il DB su Teams e rimuovi quello vecchio
        carica_elimina_teams(PATH_DATABASE, df_db, path_DB, ultimo_giorno)

        print(
            "\nSono stati caricati "
            + Fore.LIGHTBLUE_EX + f"{nuovi_record}"
            + Fore.RESET + " nuovi record...."
        )
        print(Fore.GREEN + " ✅ Caricamento avvenuto con " + Style.BRIGHT + "SUCCESSO")
        print(df_db)

    # 8. Elimina il file raw in ogni caso
    try:
        if path_raw_file.exists():
            path_raw_file.unlink()
            print(Fore.GREEN + f"✅ File raw eliminato: {path_raw_file.name}")
    except Exception as e:
        print(Fore.RED + f"⚠️ Errore nell'eliminazione del file raw: {e}")

    return True
