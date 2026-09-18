from pathlib import Path
import sys
from colorama import Fore, init
init(autoreset=True)

CARTELLA_CONSUMER = Path(__file__).resolve().parents[1]

if str(CARTELLA_CONSUMER) not in sys.path:
    sys.path.insert(0, str(CARTELLA_CONSUMER))

from common.negozi import trova_cartelle_negozi

PATH_PEDONALITA = Path.home() / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / ".parquet"
PATH_OUTPUT_REPORT = Path.home() / "My Way S.r.l" / "TEAM CONSUMER - TEAM CONSUMER"

COLONNE_TRACCIAMENTO = ["NEGOZIO", "DATA", "VENDITORE", "NOME ", "COGNOME", "NUMERO TEL.", "EMAIL", "OFFERTA", "ESITO"]


MESI_EN_IT = {
    "January": "Gennaio",
    "February": "Febbraio",
    "March": "Marzo",
    "April": "Aprile",
    "May": "Maggio",
    "June": "Giugno",
    "July": "Luglio",
    "August": "Agosto",
    "September": "Settembre",
    "October": "Ottobre",
    "November": "Novembre",
    "December": "Dicembre"
}


MAPPA_NEGOZI = {
    "Carpi"             : "CARPI",
    "Fidenza"           : "FIDENZA",
    "Parma Eurosia"     : "EUROSIA",
    "Parma Torri"       : "TORRI",
    "Piacenza Galassia" : "GALASSIA",
    "Sassuolo"          : "SASSUOLO",
}


ORDINE_MESI = [
    "Gennaio", "Febbraio", "Marzo", "Aprile",
    "Maggio", "Giugno", "Luglio", "Agosto",
    "Settembre", "Ottobre", "Novembre", "Dicembre"
]


CARTELLE_NEGOZI = {
    negozio: cartella
    for negozio, cartella in trova_cartelle_negozi().items()
    if negozio != "CARPI"
}


def trova_file(path_cartella, parametro):

    ESTENSIONI = [".xlsx", ".xlsm", ".xls", ".parquet", ".csv"]
    
    if parametro == "trattative":
        files_energia = []

        for negozio, cartella in path_cartella.items():
            file_energia = [
                file
                for ext in ESTENSIONI
                for file in cartella.rglob(f"*{ext}")
                if "energia" in file.name.lower()
            ]

            if file_energia:
                files_energia.extend(file_energia)
            else:
                print(Fore.RED + f"✕ File ENERGIA non trovato per {negozio}")

        if files_energia:
            return files_energia
        
    else:
        file_trovati = [f for ext in ESTENSIONI for f in path_cartella.glob(f"*{ext}")]
        param = parametro.strip().lower()

        for file in file_trovati:
            nome_file = file.name.lower()

            if param == "pedonalit" and "pedonalit" in nome_file:
                return Path(file)

    print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Nessun file che rispetti il parametro: {parametro}")
    sys.exit(1)
