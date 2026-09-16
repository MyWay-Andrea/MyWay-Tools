import pandas as pd
from multiprocessing import Process
from config import trova_file, PATH_DB, PATH_REPORT_FOLDER, PATH_REPORT_TEAMS, salva_report_su_teams, elimina_file_teams
from filtra_mes_set import lavora_df
from crea_popola_template import main as copia_e_popola_template, kill_excel_orfani



def run_with_timeout(func, timeout=5, *args, **kwargs):
    p = Process(target=func, args=args, kwargs=kwargs)
    p.start()
    p.join(timeout)

    if p.is_alive():
        print("⏰ Timeout raggiunto → interrompo funzione")
        p.terminate()
        p.join()
        return False

    return True

#FLUSSO PRINCIPALE
def main(path_db):
    df_db = pd.read_parquet(path_db)
    df_db = df_db.sort_values("Data", ascending = True).reset_index(drop=True)
    
    # 1. Crea colonne Anno e Mese e filtra per il mese corrente
    df_mese = lavora_df(df_db, "mese")

    # 2. stessa lavorazioni di mese ma in aggiunta settimana
    df_settimana = lavora_df(df_db, "settimana")

    if all(not df.empty for df in [df_db, df_mese, df_settimana]):
        
        # 3. trova ultimo giorno di dati
        ultimo_giorno = df_settimana["Data"].max().strftime("%d-%m-%y")

        print(df_db["Data"].head())
        # 4. Copia template e cre il nuovo report
        path_report = copia_e_popola_template(PATH_REPORT_FOLDER, df_db, df_mese, df_settimana, ultimo_giorno)

        # 5. elimina file vecchio su teams
        elimina_file_teams(PATH_REPORT_TEAMS)
        
        # 6. carica Report su Teams 
        salva_report_su_teams(path_report, PATH_REPORT_TEAMS)
    else:
        print("Uno o più df sono vuoti, operazione annulata...")

if __name__ == "__main__":
    try:
        run_with_timeout(kill_excel_orfani)
       
        path_db = trova_file(PATH_DB)
        main(path_db)
    except Exception as e:
        print(f"Lo script ha restituito un errore. esco... ERRORE --> {e}")
    
