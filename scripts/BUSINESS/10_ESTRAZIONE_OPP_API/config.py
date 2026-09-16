import pandas as pd
import os
from pathlib import Path
import sys
from colorama import Fore, init
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

BUSINESS_DIR = Path(__file__).resolve().parents[1]
if str(BUSINESS_DIR) not in sys.path:
    sys.path.insert(0, str(BUSINESS_DIR))

from common.crm_reportistica import API_KEY as REPORTISTICA_API_KEY, BASE_URL as REPORTISTICA_BASE_URL

init(autoreset=True)


'''
file configurazione per i dati dell'API e per la mapaptura dei dati
'''

API_KEY = REPORTISTICA_API_KEY
BASE_URL = REPORTISTICA_BASE_URL

# PERCORSI
PATH_HOME           = Path.home()
PATH_DIR            = Path(
    os.environ.get(
        "MYWAY_SHAREPOINT_ROOT",
        PATH_HOME / "My Way S.r.l" / "MyWay Tools - MyWay Tools",
    )
)

#path input
PATH_RAW_FILE = PATH_DIR / "SCRIPT" / "00_RAW_FILE"

#path output
PERCORSO_TEAMS         = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI"
PATH_PARQUET           = PERCORSO_TEAMS / ".parquet"
PATH_BASI_DATI         = PERCORSO_TEAMS / "BASI_DATI_xlsx"
PATH_STORICO_BASI_DATI = PATH_BASI_DATI / "STORICO"


STATO_MAP = {
    59096 : "Aperta",
    59101 : "Persa",
    59100 : "Acquisita",
}

TIP_SERVIZIO_MAP = {

    "1": "ALTRO",
    "2": "SIM VOCE",
    "3": "SIM DATI",
    "4": "DSL",
    "5": "ON TOP DSL",
    "6": "VRU INTERNO",
    "7": "LINK SA",
    "8": "LINK SU",
    "9": "TW SA",
    "10": "ON TOP LINK",
    "11": "M2M",
    "12": "SAAS",
    "13": "COLLABORATION",
    "14": "IAAS",
    "15": "SECURITY",
    "16": "COMPLEX DEAL",
    "17": "CUSTOM APP",
    "18": "EASY DEAL",
    "19": "EOLO",
    "20": "RATA TEL",
    "21": "SOL TEL",
    "22": "RATA TEL VOCE",
    "23": "SOL TEL VOCE",
    "24": "ON TOP EASY DEAL",
    "25": "RATA TEL DATI",
    "26": "SOL TEL DATI",
    "27": "NOLEGGIO OP."
}

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

COLONNE_OPPORTUNITA = [
    "Codice Opportunità",
    "Potenziale cliente (Opportunità)",
    "Partita IVA (Opportunità)",
    "Proprietario (Opportunità)",
    "Stato (Opportunità)",
    "Data creazione",
    "Data chiusura prev. (Opportunità)",
    "Data modifica",
    "Tipologia Servizio",
    "Prodotto esistente",
    "Quantità",
    "Prezzo",
    "Importo totale",
    "Probabilità (Opportunità)",
]


def trova_file(path_cartella: Path, parametro: str) -> Path:
    estensioni = ["*.xlsx", "*.xlsm", "*.xls", "*.parquet", "*.csv"]
    file_trovati = [file for estensione in estensioni for file in path_cartella.glob(estensione)]

    for file in file_trovati:
        nome_file = file.name.lower()
        if parametro == "Opportunità" and "opportunita" in nome_file:
            return file
        if parametro == "Storico" and "storico opportunita" in nome_file:
            return file

    print(f"[{Fore.RED}ERRORE{Fore.RESET}] Nessun file che rispetti il parametro: {parametro}")
    sys.exit(1)


def _formatta_excel(path: Path) -> None:
    col_prezzi = set()
    col_date = set()
    col_prob = set()

    wb = load_workbook(path)
    ws = wb.active

    fill_blu = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    fill_giallo = PatternFill(start_color="FFD966", end_color="FFD966", fill_type="solid")
    fill_rosso = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    font_bianco = Font(color="FFFFFF", bold=True)
    font_nero = Font(color="000000", bold=True)
    font_verde_testo = Font(color="2FBF47", bold=True)
    font_arancione_testo = Font(color="EA6B14", bold=True)
    font_rosso_testo = Font(color="FF0000", bold=True)
    font_azzurro_testo = Font(color="00B0F0", bold=True)

    for cella in ws[1]:
        nome_colonna = str(cella.value).strip().lower() if cella.value else ""

        if "proprietario" in nome_colonna:
            cella.fill = fill_giallo
            cella.font = font_nero
        elif "probabilit" in nome_colonna:
            cella.fill = fill_rosso
            cella.font = font_bianco
        else:
            cella.fill = fill_blu
            cella.font = font_bianco

        if "prezzo" in nome_colonna or "importo" in nome_colonna:
            col_prezzi.add(cella.column)
        elif "data" in nome_colonna:
            col_date.add(cella.column)
        elif "probabilit" in nome_colonna:
            col_prob.add(cella.column)

    for riga in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cella in riga:
            if cella.column in col_date:
                cella.number_format = "DD/MM/YYYY"
            elif cella.column in col_prezzi:
                cella.number_format = "#,##0.00 €"
            elif cella.column in col_prob:
                cella.number_format = r"0\%"
            elif str(cella.value).strip().lower() == "aperta":
                cella.font = font_verde_testo
            elif str(cella.value).strip().lower() == "acquisita":
                cella.font = font_azzurro_testo
            elif str(cella.value).strip().lower() == "persa":
                cella.font = font_rosso_testo

    wb.save(path)


def carica_su_teams(df: pd.DataFrame, *paths: Path) -> None:
    try:
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Atteso pandas.DataFrame, ricevuto {type(df).__name__}")

        for path in paths:
            if ".parquet" in path.name:
                df.to_parquet(path / "opportunita.parquet", index=False)
            elif "BASI_DATI_xlsx" in path.name:
                file_output = path / "opportunita.xlsx"
                df.to_excel(file_output, index=False, engine="openpyxl")
                _formatta_excel(file_output)
            elif ".parquet" in path.parent.name and "STORICO" in path.name:
                df.to_parquet(path / "Storico Opportunita.parquet", index=False)
            elif "BASI_DATI_xlsx" in path.parent.name and "STORICO" in path.name:
                file_output = path / "Storico Opportunita.xlsx"
                df.to_excel(file_output, index=False, engine="openpyxl")
                _formatta_excel(file_output)

        print(Fore.GREEN + "✅ Caricamento su Teams avvenuto con successo\n")
    except Exception as errore:
        print(f"[{Fore.RED}ERRORE{Fore.RESET}] Caricamento file su Teams fallito --> {errore}")


def elimina_file(file_path: Path) -> None:
    if file_path.is_file():
        file_path.unlink()
