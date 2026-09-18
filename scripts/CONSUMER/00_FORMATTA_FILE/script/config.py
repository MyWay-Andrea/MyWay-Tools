from pathlib import Path
import io
import contextlib
import os

# IMPORT PERCORSI UTILILI
#-------------------------------------------------------------------------------------------------

PATH_DIR = Path(__file__).parents[4]

PATH_RAW_FILES = PATH_DIR / "SCRIPT" / "00_RAW_FILE"
PATH_FORMATTA_PEDONALITA = PATH_DIR / "SCRIPT" / "CONSUMER" / "01_FORMATTA_PEDONALITA" / "script" / "AGGREGA_FILE.py"
PATH_FORMATTA_MAGAZZINO = PATH_DIR / "SCRIPT" / "CONSUMER" / "03_FORMATTA_MAGAZZINO" / "script" / "formatta_magazzino.py"

PATH_CONSUMER = PATH_DIR / "SCRIPT" / "CONSUMER"

def trova_file(path_folder, filtro: str):
    estensioni = ["*.csv", "*.xlsx", "*.xls"]
    file_trovati = [f for ext in estensioni for f in path_folder.glob(ext)]

    for file in file_trovati:
        nome = file.name.lower()
        if filtro is None:
            raise ValueError("❌ Manca filtro")
        elif filtro in nome:
            print(f" 📁 File '{filtro}' trovato: {file.name}\n")
            return file

    
    raise FileNotFoundError(f"❌ Nessun file trovato con filtro '{filtro}' in {path_folder}")
        

# PER ESEGUIRE FUNZIONI SENZA MOSTRARE I "PRINT"
#-------------------------------------------------------------------------------------------------
def run_silenzioso(func, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return func(*args, **kwargs)