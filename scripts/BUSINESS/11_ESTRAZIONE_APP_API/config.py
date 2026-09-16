import os
import sys
from pathlib import Path

import pandas as pd
from colorama import Fore, init
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

BUSINESS_DIR = Path(__file__).resolve().parents[1]
if str(BUSINESS_DIR) not in sys.path:
    sys.path.insert(0, str(BUSINESS_DIR))

from common.crm_reportistica import API_KEY as REPORTISTICA_API_KEY, BASE_URL as REPORTISTICA_BASE_URL

init(autoreset=True)

API_KEY = REPORTISTICA_API_KEY
BASE_URL = REPORTISTICA_BASE_URL

PATH_HOME = Path.home()
PATH_DIR = Path(
    os.environ.get(
        "MYWAY_SHAREPOINT_ROOT",
        PATH_HOME / "My Way S.r.l" / "MyWay Tools - MyWay Tools",
    )
)
PATH_RAW_FILE = PATH_DIR / "SCRIPT" / "00_RAW_FILE"
PERCORSO_TEAMS = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI"
PATH_PARQUET = PERCORSO_TEAMS / ".parquet"
PATH_BASI_DATI = PERCORSO_TEAMS / "BASI_DATI_xlsx"
PATH_STORICO_BASI_DATI = PATH_BASI_DATI / "STORICO"

CONVERSIONE_NOMI = {
    "Giorgio Mandelli": "G.MANDELLI",
    "Giovanni Marra": "G.MARRA",
    "Eduart Agalliu": "E.AGALLIU",
    "Alberto Milani": "A.MILANI",
    "Danilo Carugo": "D.CARUGO",
    "Doriano Gnani": "D.GNANI",
    "Enrico Pignatta": "E.PIGNATTA",
    "Mauro Sala": "M.SALA",
    "Riccardo Scimone": "R.SCIMONE",
    "Fabio Arlotta": "F.ARLOTTA",
    "CRM MWR": "CRM My Way",
}

COLONNE_APPUNTAMENTI = [
    "Data",
    "Orario",
    "Cliente",
    "In carico a",
    "Accompagnato da",
    "Indirizzo",
    "Fatta/da fare",
    "Tipo di appuntamento",
    "Nota interna",
]

# Valori confermati nel campione API di Activity/Search.
TIPO_ATTIVITA_APPUNTAMENTO = 6

STATO_ATTIVITA_MAP = {
    0: "Attività da fare",
    1: "Annullata",
    2: "Attività fatta",
}

TIPO_APP_MAP = {
    "1": "CB",
    "2": "Autoprocurato CB",
    "3": "Prospect",
    None: "NON IDNICATO"
}


def trova_file(path_cartella: Path, parametro: str) -> Path:
    estensioni = ["*.xlsx", "*.xlsm", "*.xls", "*.parquet", "*.csv"]
    file_trovati = [file for estensione in estensioni for file in path_cartella.glob(estensione)]
    for file in file_trovati:
        nome_file = file.name.lower()
        if parametro == "Appuntamenti" and "appuntamenti" in nome_file:
            return file
        if parametro == "Storico" and "storico appuntamenti" in nome_file:
            return file

    print(f"[{Fore.RED}ERRORE{Fore.RESET}] Nessun file che rispetti il parametro: {parametro}")
    sys.exit(1)


def _formatta_excel(path: Path) -> None:
    col_date = set()
    wb = load_workbook(path)
    ws = wb.active

    fill_blu = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    fill_giallo = PatternFill(start_color="FFD966", end_color="FFD966", fill_type="solid")
    font_bianco = Font(color="FFFFFF", bold=True)
    font_nero = Font(color="000000", bold=True)
    font_verde = Font(color="2FBF47", bold=True)
    font_rosso = Font(color="FF0000", bold=True)
    font_azzurro = Font(color="00B0F0", bold=True)

    for cella in ws[1]:
        nome_colonna = str(cella.value).strip().lower() if cella.value else ""
        if "in carico a" in nome_colonna:
            cella.fill = fill_giallo
            cella.font = font_nero
        else:
            cella.fill = fill_blu
            cella.font = font_bianco
        if "data" in nome_colonna:
            col_date.add(cella.column)

    for riga in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cella in riga:
            valore = str(cella.value).strip().lower()
            if cella.column in col_date:
                cella.number_format = "DD/MM/YYYY"
            elif valore == "attività fatta":
                cella.font = font_verde
            elif valore == "attività da fare":
                cella.font = font_azzurro
            elif valore == "annullata":
                cella.font = font_rosso
    wb.save(path)


def carica_su_teams(df: pd.DataFrame, *paths: Path) -> None:
    try:
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Atteso pandas.DataFrame, ricevuto {type(df).__name__}")

        for path in paths:
            if ".parquet" in path.name:
                df.to_parquet(path / "Appuntamenti.parquet", index=False)
            elif "BASI_DATI_xlsx" in path.name:
                file_output = path / "Appuntamenti.xlsx"
                df.to_excel(file_output, index=False, engine="openpyxl")
                _formatta_excel(file_output)
            elif ".parquet" in path.parent.name and "STORICO" in path.name:
                df.to_parquet(path / "Storico Appuntamenti.parquet", index=False)
            elif "BASI_DATI_xlsx" in path.parent.name and "STORICO" in path.name:
                file_output = path / "Storico Appuntamenti.xlsx"
                df.to_excel(file_output, index=False, engine="openpyxl")
                _formatta_excel(file_output)

        print(Fore.GREEN + "✅ Caricamento su Teams avvenuto con successo\n")
    except Exception as errore:
        print(f"[{Fore.RED}ERRORE{Fore.RESET}] Caricamento file su Teams fallito --> {errore}")
        raise
