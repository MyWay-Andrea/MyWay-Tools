from pathlib import Path
from datetime import datetime 
import time

PATH_HOME = Path.home()
PATH_DATABASE = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / ".parquet"

OGGI = datetime.today()
OGGI_STRF = OGGI.strftime("%d-%m-%Y")

import os
_app_dir = os.environ.get("BASE_DIR")
if _app_dir:
    PATH_DIR = Path(_app_dir)
else:
    PATH_DIR = Path(__file__).parents[5]

PATH_RAW_FOLDER = PATH_DIR / "00_RAW_FILE"

#FUNZIONI COMUNI
#---------------------------------------------------------------

#FUNZIONE PER TROVARE E CONTROLLARE LA CARTELLA "RAW_PEDONALITA"
#--------------------------------------------------------------
def trova_file(path_cartelle):
    ESTENSIONI = ["*.parquet", "*.xlsx"]
    ped_DB = None
    pedonalita_lavorata  = []
    
    file_trovati = [f for ext in ESTENSIONI for f in path_cartelle.glob(ext)]

    for file in file_trovati:
        nome = file.name.lower()
        if "giorgio" in nome:
            pedonalita_lavorata.append(file)
        elif "pedonalit" in nome:
            ped_DB = file
        
    
    raw_ped = pedonalita_lavorata[-1] if pedonalita_lavorata else None

    if ped_DB is None and raw_ped:
        print(f"    📁 Pedonalita Preparata:    {raw_ped}\n")
    elif ped_DB and raw_ped is None:
        print(f"    📁 Pedonalita DataBase:    {ped_DB}\n")
    elif ped_DB and raw_ped:
        print(f"    📁 Pedonalita DataBase:    {ped_DB}")
        print(f"    📁 Pedonalita Preparata:    {raw_ped}\n")
    else:
        print("    ❌ Nessun file di pedonalità trovato nella cartella Raw Folder.")

    return ped_DB, raw_ped, 


#---------------------------------------------------------------

#FILE:
#PREPARA PEDONALITA
#-------------------------------------------------------------------------


NEGOZIO_CONDITION = {
    "28657.0W021" : "Fidenza",
    "28657.0W022" : "Piacenza Galassia",
    "28657.0W100" : "Parma Torri",
    "28657.0W101" : "Parma Eurosia",
    "28657.0W409" : "Modena",
    "28657.0W728" : "Sassuolo",
    "28657.0X132" : "Carpi",
    "28657.0Z889" : "Piacenza Centro"
}

COLONNE_ORDINATE = ["Negozio", "Data", "Ora", "Giorno","Giorno_num", "Fascia oraria", "Presenze" ]

#-------------------------------------------------------------------------

#FILE:

#AGGREGA_FILE
#-------------------------------------------------------------------------
             
def salva_su_teams_parquet(path, df, ultimo_giorno):
    
    #assegnazione percorso al nome perchè parquet non permette di assegnarli separatamente
    filename = path / f"Pedonalità_{ultimo_giorno}.parquet"
    #salvataggio file 
    df.to_parquet(filename)
    
def salva_su_teams_excel(path, df, ultimo_giorno):
    percorso = path.parent

    filename = percorso / "BASI_DATI_xlsx" / f"Pedonalità_{ultimo_giorno}.xlsx"

    df.to_excel(filename)
#-------------------------------------------------------------------------

def elimina_file_da_cartella(file, ultimo_giorno, estensione):
    if estensione == "parquet" or estensione == "xlsx":
        if file.exists():
            file.unlink()
            print(f"\n  ✅ file {file.name} è stato rimosso per far spazio al nuovo Pedonalità_{ultimo_giorno}.{estensione} ")
        time.sleep(1)
        if file.exists():
           print("Il file non è stato cancellato ")
   



def elimina_file_da_cartella(path_dir, ultimo_giorno):
    #elimina file veechio in base al nome "Pedonalità"
    path_dir = Path(path_dir)
    path_xlsx = path_dir.parent / "BASI_DATI_xlsx"
    for path in [path_xlsx, path_dir]:
        for ext in ["*.parquet", "*.xlsx"]:
            for file in path.glob(ext):
                if f"Pedonalità" in file.name:
                    if file.exists():
                        file.unlink()
                        print(f"\n  ✅ file {file.name} è stato rimosso per far spazio al nuovo Pedonalità_{ultimo_giorno}{ext} ")
                    time.sleep(1)
                    if file.exists():
                       print("Il file non è stato cancellato ")