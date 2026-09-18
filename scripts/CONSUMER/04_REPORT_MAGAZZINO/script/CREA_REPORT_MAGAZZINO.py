import pandas as pd
from config import trova_file, NOME_REPORT, PATH_TEMPLATE, PATH_DB, PATH_REPORT_FOLDER, PATH_REPORT_TEAMS, elimina_file_vecchio, kill_excel_orfani
import shutil
import xlwings as xw
import time
from colorama import Fore, init
init(autoreset=True, convert=True)

#CREA FILE E AGGIORNA LE PIVOT
#-------------------------------------------------------------------------
def crea_e_aggiorna_file(output_file, dati_magazzino):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PATH_TEMPLATE, output_file)
    
    for _ in range(5):
        if output_file.exists():
            break
        time.sleep(0.5)
    
    
    app = xw.App(visible=False)
    app.display_alerts = False
    try:
        wb = xw.Book(output_file)
        
        # Scrittura dati
        ws_db = wb.sheets["DB"]
        ws_db.range("A2").value = dati_magazzino.values.tolist()
        
        # Refresh pivot
        wb.api.RefreshAll()
        ws_pivot = wb.sheets["REPORT"]
        ws_pivot.autofit('columns')

        wb.save()
        wb.close()
    finally:
        app.quit()

#CICLO PRINCIPALE
#-------------------------------------------------------------------------
def main(df_magazzino, path_output):

    steps = [
        ("Creazione file performance", lambda: crea_e_aggiorna_file(path_output, df_magazzino)),
        ("Eliminazione file magazzino vecchio", lambda: elimina_file_vecchio(PATH_REPORT_TEAMS)),
        ("Salvataggio file su Teams", lambda: shutil.copy2(path_output, PATH_REPORT_TEAMS))
    ]
    
    for descrizione, step in steps:
        try:
            print(f"Elaborazione: {Fore.YELLOW}{descrizione}...")
            step()
            print(f" ✅ {descrizione} completata\n")
        except Exception as e:
            print(Fore.RED + f" ❌ ERRORE in '{descrizione}' --> {e}")
            quit()
        
    print(Fore.GREEN + "\nSCRIPT ESEGUITO CON SUCCESSO")

if __name__ == "__main__":
    try:  
          
        kill_excel_orfani()
        path_file = trova_file(PATH_DB)
        PATH_OUTPUT_FILE = PATH_REPORT_FOLDER / NOME_REPORT   
        df = pd.read_parquet(path_file)
        main(df, PATH_OUTPUT_FILE)

    except Exception as e:

        print(f"Lo script ha restituito un errore. esco... ERRORE --> {e}")