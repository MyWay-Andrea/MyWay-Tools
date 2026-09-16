from pathlib import Path
import sys
from datetime import datetime
from colorama import Fore, init
init(autoreset = True)


#VARIABILI GLOBALI

PATH_HOME = Path.home()

PATH_DIR = Path(__file__).parents[4]
PATH_ONEDRIVE_FILE = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / ".parquet" 
PATH_OUTPUT_FCST = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" 


RICERCA_FILES = ["gara", "opportunita", "appuntamenti"]

PERIODO_GARE = {
    1: "Gen - Mar",
    2: "Gen - Mar",
    3: "Gen - Mar",
    4: "Apr - Giu",
    5: "Apr - Giu",
    6: "Apr - Giu",
    7: "Lug - Set",
    8: "Lug - Set",
    9: "Lug - Set",
    10: "Ott - Dic",
    11: "Ott - Dic",
    12: "Ott - Dic",
}

MESI_IT = {
    1: "Gennaio",
    2: "Febbraio",
    3: "Marzo",
    4: "Aprile",
    5: "Maggio",
    6: "Giugno",
    7: "Luglio",
    8: "Agosto",
    9: "Settembre",
    10: "Ottobre",
    11: "Novembre",
    12: "Dicembre",
}


#FUNZIONI
def trova_file(path: Path, param:str) -> Path:

    ricerca = param.strip().lower()

    estensioni = ["*.xlsx", "*.xls", "*.csv", "*.parquet"]
    file_presenti = [file for ext in estensioni for file in path.glob(ext)]

    for f in file_presenti:
        
        nome_file = f.name.strip().lower()

        if ricerca in nome_file:
            print(Fore.GREEN + "✓ " + Fore.RESET + f"{f.name}")
            return f
        else:
            continue

    print("[" + Fore.RED + "ERRORE" + Fore.RESET + f"] file '{param}' non presente nella cartella {path}")  
    sys.exit(1)

def trova_periodo_gara():
    oggi = datetime.today()
    anno = oggi.year
    gara_corrente = PERIODO_GARE[oggi.month]

    if gara_corrente == "Gen - Mar":
        mesi = [1, 2, 3]
    elif gara_corrente == "Apr - Giu":
        mesi = [4, 5, 6]
    elif gara_corrente == "Lug - Set":
        mesi = [7, 8, 9]
    else:
        mesi = [10, 11, 12]

    return anno, mesi, gara_corrente

        
            

    
