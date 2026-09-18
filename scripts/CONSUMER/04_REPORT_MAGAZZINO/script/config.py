from pathlib import Path
import time
from datetime import datetime
import psutil

'''
PER ESTRARRE IL FILE DEL MAGAZZINO BISOGNA ANDARE SU:
StoreSales > Categorie(TUTTE) > P.Vendita(TUTTI) > Ordina per (CATEGORIA) > FILTRA
ps. scaricare il file in formato "CSV"
'''


PATH_DIR = Path(__file__).parents[3]

PATH_HOME = Path.home()

PATH_DB = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / ".parquet"
PATH_REPORT_TEAMS = PATH_HOME / "My Way S.r.l" / "TEAM CONSUMER - TEAM CONSUMER"

PATH_TEMPLATE = PATH_DIR / "SCRIPT" / "CONSUMER" / "TEMPLATE" / "TEMPLATE_MAGAZZINO.xlsx"
PATH_REPORT_FOLDER = PATH_DIR / "SCRIPT" / "CONSUMER" / "report" 

DATA_OGGI = datetime.now().strftime("%d-%m-%Y")
NOME_REPORT = f"GIACENZE_MAGAZZINO_{DATA_OGGI}.xlsx"

def trova_file(path_folder: Path):

    file_trovati =[f for f in path_folder.glob("*.parquet")]
    
    for file in file_trovati:
        nome = file.name.lower()
        if "magazzino" in nome:
            print(f" 📁 File magazzino trovato: {file.name}\n")
            return file
        
    raise FileNotFoundError("❌ Nessun file del magazzino trovato nella cartella")

def elimina_file_vecchio(path_teams):
    files = [f for f in path_teams.glob("GIAGENZE_*xlsx")]
    for file in files:
        file.unlink()
        time.sleep(1)
        if file.exists():
            print(" ❌ ERRORE --> File non cancellato correttamente")
            break


#ELIMINA PROCESSI EXCEL RIMASTI APERTI
def kill_excel_orfani():

    uccisi = 0
    for processo in psutil.process_iter(["name"]):
        try:
            if processo.info['name'] == "EXCEL.EXE":
                processo.kill()
                uccisi += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if uccisi:
        print(f"Chiusi {uccisi} processi Excel orfani")
        time.sleep(1)