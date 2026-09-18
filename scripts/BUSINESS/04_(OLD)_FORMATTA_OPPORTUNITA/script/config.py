from pathlib import Path
from copy import copy
import pandas as pd
import shutil
import sys
import os 
from colorama import Fore, Style, init
init(autoreset=True) # Resetta il colore automaticamente dopo ogni print

PATH_HOME = Path.home()


PATH_DIR = Path(__file__).parents[4]

DEST = PATH_DIR / "SCRIPT" / "BUSINESS" / "04_FORMATTA_OPPORTUNITA" / "script" / "file_generati_last"
PERCORSO_TEAMS = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI"
PATH_PARQUET = PERCORSO_TEAMS / ".parquet"
PATH_RAW_FILE = PATH_DIR / "SCRIPT" / "00_RAW_FILE"
#FORMATTA OPPORTUNITà
#------------------------------------------------------------------
FILTRO_STATO = ["Aperta"]
LISTA_COLONNE_OPPORTUNITA = [2, 4, 10, 17, 12, 9, 19, 27, 28, 29, 6, 5]
COLONNA_AGENTE_OPP = "Proprietario (Opportunità)"
MASTER_OPPORTUNITA = PATH_DIR / "SCRIPT" / "BUSINESS" / "04_FORMATTA_OPPORTUNITA" / "template" / "TEMPLATE_OPPORTUNITA.xlsx"
SHEET_OPPORTUNITA = "OPPORTUNITA"
DATE_COLS_NAME_OPP = [' "Data Chiusura Prevista"', ' "Orario modifica"', ' "Orario creazione"']
#------------------------------------------------------------------

def copia_formattaz_cella(cella_input, cella_output):
    if cella_input.has_style:
        cella_output.font = copy(cella_input.font)
        cella_output.border = copy(cella_input.border)
        cella_output.fill = copy(cella_input.fill)
        cella_output.number_format = copy(cella_input.number_format)
        cella_output.protection = copy(cella_input.protection)
        cella_output.alignment = copy(cella_input.alignment)

def copia_template(file_master, file=None, nome=None):
    if file:
        file_output = DEST / file.name
    elif nome:
        file_output = DEST / nome
    else:
        print(Fore.RED + " ❌   MANCANZA DI NOME E/O PERCORSO")
        return None
    DEST.mkdir(parents=True, exist_ok=True)
    shutil.copy(file_master, file_output)
    return file_output

def copia_su_teams(file_gara, path_teams = None):
    if isinstance(file_gara, pd.DataFrame):
        file_gara.to_parquet(PATH_PARQUET / "Opportunità.parquet", index = False)
    elif file_gara is not None and path_teams is not None:
        filename = path_teams / file_gara.name
        shutil.copy2(file_gara, filename)

def trova_raw_file(path_cartella):
    ESTENSIONI = ["*.xlsx", "*.xlsm", "*.xls", "*.csv"]
    file_trovati = [f for ext in ESTENSIONI for f in path_cartella.glob(ext)]

    file_opportunit = None
    for file in file_trovati:
        print(f" ⚠️ file trovato: {file}")
        if "opportunit" in file.name.lower():
            try:
                file_opportunit = file.rename(file.parent / "Opportunità.csv")
                print(f" 🖊️ Rinomina in '{file_opportunit.name}' andata a BUON fine")
            except Exception as e:
                print(f" ⚠️ Rinomina fallita: {e}")
                file_opportunit = file

    if file_opportunit is None:
        print(Fore.RED + " ❌ Nessun file 'opportunit' trovato nella cartella raw_file.")
        sys.exit(1)

    return file_opportunit

#FUNZIONE PER SELIMINARE IL FILE GARA DALLA CARTELLA 
#---------------------------------------------------------------------------
def svuota_cartella(cartella, nome_file):
    if nome_file is None:
        print(" ❌ ERRORE --> manca il nome del file da eliminare")
        return
    else:
        for file in cartella.iterdir():
            if file.is_file() and nome_file in file.name.lower() :
                file.unlink()
                print(f" 🗑️ File eliminato da {cartella}: {file.name}")