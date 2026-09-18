from pathlib import Path
from datetime import datetime 
import shutil
import time

oggi = datetime.today()
OGGI_STRF = oggi.strftime(format = "%d-%m-%y")

PATH_DIR = Path(__file__).parents[1]

PATH_HOME = Path.home()
PATH_TEMPLATE = PATH_DIR / "TEMPLATE" / "TEMPLATE_PEDONALITA.xlsx"
PATH_REPORT_FOLDER = PATH_DIR / "report"
PATH_REPORT_TEAMS = PATH_HOME / "My Way S.r.l" / "TEAM CONSUMER - TEAM CONSUMER"
PATH_DB = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / ".parquet"


#FUNZIONE PER TROVARE E CONTROLLARE LA CARTELLA "RAW_PEDONALITA"
#--------------------------------------------------------------
def trova_file(path_cartella):
    ESTENSIONI = ["*.parquet"]
    ped_DB = None
    file_trovati = [f for ext in ESTENSIONI for f in path_cartella.glob(ext)]

    for file in file_trovati:
        nome = file.name.lower()
        if "pedonalit" in nome:
            ped_DB = file
    
    print(f" 📁 Pedonalità DataBase:    {ped_DB}")


    return ped_DB
#SALVA SU TEAMS 
#----------------------------------------------------------------
def salva_report_su_teams(report, path_teams):
    path_report = Path(report)
    filename = path_teams / path_report.name
    shutil.copy2(path_report, filename)
    print(f" ✅ Report salvato su Teams: {filename}")

#ELIMINA FILE VECCHIO SU TEAMS
#----------------------------------------------------------------
def elimina_file_teams(PATH_TEAMS):
    filename = "REPORT_PEDONALITA*.xlsx"
    
    files = list(PATH_TEAMS.glob(filename))
    
    if not files:
        print("⚠️ Nessun file trovato")
        return

    for file in files:
        while True:
            try:
                file.unlink()
                time.sleep(1)
                if file.exists():
                    print(f"❌ {file.name} non è stato cancellato, riprovo...")
                else:
                    print(f"✅ {file.name} eliminato con successo!")
                    break
            except Exception as e:
                print(f"Errore su {file.name}: {e}")
                break
