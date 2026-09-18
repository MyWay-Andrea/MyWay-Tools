from pathlib import Path
from copy import copy
import pandas as pd
import shutil
import sys
import os
from colorama import Fore, Style, init
init(autoreset=True)

PATH_HOME = Path.home()


PATH_DIR = Path(__file__).parents[4]


DEST = PATH_DIR / "SCRIPT" / "BUSINESS" / "03_FORMATTA_GARA" / "file_generati_last"

PERCORSO_TEAMS = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI"
PATH_PARQUET = PERCORSO_TEAMS / ".parquet"

# FORMATTA GARA
COLONNE = [0, 1, 2, 3, 4, 5, 6, 17, 8, 9, 10, 11, 12, 13, 14, 15, 16]
SERVIZI_DA_SCONTARE = ["SIM VOCE", "SIM DATI", "VRU INTERNO"]
COLONNA_AGENTE_GARA = "Proprietario (Ordine)"
MASTER_GARA = PATH_DIR / "SCRIPT" / "BUSINESS" / "03_FORMATTA_GARA" / "template" / "TEMPLATE_GARA.xlsx"
DATE_COLS = [8, 9, 10, 11]
DATE_COLS_NAME = ['Ordini di vendita Orario creazione', 'Items D.I.B.S.', 'Items D.P.A.', 'Items D.A.']
SHEET_GARA = "GARA"
PATH_RAW_FILE = PATH_DIR / "SCRIPT" / "00_RAW_FILE"


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
        #file_gara.to_parquet(PATH_PARQUET / "Gara (inflow).parquet", index = False)
        print("ciao")
    elif file_gara is not None and path_teams is not None:
        filename = path_teams / "BASI_DATI_xlsx" /file_gara.name
        print(filename)
        shutil.copy2(file_gara, filename)


def trova_raw_file(path_cartella):
    ESTENSIONI = ["*.xlsx", "*.xlsm", "*.xls", "*.csv"]
    file_trovati = [f for ext in ESTENSIONI for f in path_cartella.glob(ext)]

    file_gara = None
    for file in file_trovati:
        print(f" ⚠️ file trovato: {file}")
        if "inflow" in file.name.lower():
            try:
                file_gara = file.rename(file.parent / "Gara (Inflow).xlsx")
                print(f" 🖊️ Rinomina in '{file_gara.name}' andata a BUON fine")
            except Exception as e:
                print(f" ⚠️ Rinomina fallita: {e}")
                file_gara = file

    if file_gara is None:
        print(Fore.RED + " ❌ Nessun file 'inflow' trovato nella cartella raw_file.")
        sys.exit(1)

    return file_gara

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

        