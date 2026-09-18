from pathlib import Path
from datetime import datetime
import time


'''
PER ESTRARRE IL FILE DEL MAGAZZINO BISOGNA ANDARE SU:
StoreSales > Categorie(TUTTE) > P.Vendita(TUTTI) > Ordina per (CATEGORIA) > FILTRA
ps. scaricare il file in formato "CSV"
'''

OGGI = datetime.today().strftime(format = "%d-%m-%Y")
PATH_HOME = Path.home()
PATH_DIR = Path(__file__).parents[3]

PATH_RAW_FOLDER = PATH_DIR / "SCRIPT" / "00_RAW_FILE"
PATH_TEAMS = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI"


def trova_file(path_folder):
    estensioni = ["*.csv", "*.xlsx"]
    file_trovati =[f for ext in estensioni for f in path_folder.glob(ext)]

    for file in file_trovati:
        nome = file.name.lower()
        if "valore_del_magazzino" in nome:
            print(f" 📁 File magazzino trovato: {file}\n")
            return file
    
#SALVA SU TEAMS IN FORMATO XLSX E .PARQUET
#--------------------------------------------------------
def salva_su_teams(path_folder, df,):

    #salvataggio percorsi xlsx e .parquet
    filename = Path(path_folder) / ".parquet" / f"Magazzino_{OGGI}.parquet"
    filename_excel = Path(path_folder) / "BASI_DATI_xlsx" / f"Magazzino_{OGGI}.xlsx"
    
    #salvataggio in entrambe le versioni
    df.to_parquet(filename, index=False)
    df.to_excel(filename_excel, index=False)    

    print(f" ✅ File salvato su Teams: {filename_excel} e {filename}")

def elimina_file_RAW(file):
    if file.exists():
        file.unlink()
    time.sleep(1)
    if file.exists():
       print("Il file non è stato cancellato ")  


def elimina_file_teams(PATH_TEAMS):
    estensioni = ["*.parquet", "*.xlsx"]

    path_xslx = PATH_TEAMS / "BASI_DATI_xlsx"
    path_parquet = PATH_TEAMS / ".parquet"
    
    cartelle = [path_xslx, path_parquet]

    for dir in cartelle:
        file_trovati =[f for ext in estensioni for f in dir.glob(ext)]
        for file in file_trovati:
            nome = file.name.lower()
            if "magazzino" in nome:
                print(f" 🧹 Eliminazione file precedente: {file}")
                file.unlink()