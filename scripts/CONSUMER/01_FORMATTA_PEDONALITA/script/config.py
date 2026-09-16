from pathlib import Path
import os
from datetime import datetime 
import time
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from colorama import Fore, init, Back
init(autoreset=True)


PATH_HOME = Path.home()
PATH_DATABASE = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / ".parquet"
PATH_TEAM_CONSUMER = PATH_HOME / "My Way S.r.l" / "TEAM CONSUMER - TEAM CONSUMER"/ "_file_report"
OGGI = datetime.today()
OGGI_STRF = OGGI.strftime("%d-%m-%Y")

PATH_DIR = Path(
    os.environ.get(
        "MYWAY_SHAREPOINT_ROOT",
        PATH_HOME / "My Way S.r.l" / "MyWay Tools - MyWay Tools",
    )
)


PATH_RAW_FOLDER = PATH_DIR / "SCRIPT" / "00_RAW_FILE" 

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
        print(f" 📁 Pedonalita Preparata:    {raw_ped}\n")
    elif ped_DB and raw_ped is None:
        print(f" 📁 Pedonalita DataBase:    {ped_DB}\n")
    elif ped_DB and raw_ped:
        print(f" 📁 Pedonalita DataBase:    {ped_DB}")
        print(f" 📁 Pedonalita Preparata:    {raw_ped}\n")
    else:
        print(" ❌ Nessun file di pedonalità trovato nella cartella Raw Folder.")
        
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

COLONNE_ORDINATE = ["Negozio", "Data", "Ora", "Giorno","Giorno_num", "Fascia oraria", "Presenze"]

#-------------------------------------------------------------------------

#FILE:

#AGGREGA_FILE
#-------------------------------------------------------------------------
def formatta_colonna_data(filename, df):
    

    wb = load_workbook(filename)
    ws = wb.active

    # trova colonna "Data"
    col_data_idx = None
    for i, col_name in enumerate(df.columns, start=1):
        if col_name == "Data":
            col_data_idx = i
            break

    if col_data_idx:
        col_letter = get_column_letter(col_data_idx)
        for cell in ws[col_letter][1:]:
            cell.number_format = 'DD/MM/YYYY'

    wb.save(filename)

def salva_su_teams_excel(filename, df):
    
    df.to_excel(filename, index=False)
    time.sleep(1)
    formatta_colonna_data(filename, df)

#-------------------------------------------------------------------------


def elimina_file_da_cartella(path_basi_dati , path_consumer, path_parquet, ultimo_giorno):
    #elimina file veechio in base al nome "Pedonalità"
    print(" ⏳ Eliminazione file datati...")
    lista_path = [path_basi_dati , path_consumer, path_parquet]
    for path in lista_path:
        print(f"\n • Cartella: " + Fore.BLACK + Back.WHITE + f" {path.name} ")
        for ext in ["*.parquet", "*.xlsx"]:
            for file in path.glob(ext):
                if f"Pedonalità" in file.name:
                    if file.exists():
                        file.unlink()
                        print(f" ✅ file {file.name} è stato rimosso per far spazio al nuovo Pedonalità_{ultimo_giorno}{ext} ")
                    time.sleep(1)
                    if file.exists():
                       print("Il file non è stato cancellato ")
