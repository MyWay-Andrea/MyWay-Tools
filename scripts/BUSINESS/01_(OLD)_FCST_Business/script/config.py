from pathlib import Path
from colorama import Fore
from tqdm import tqdm
import pandas as pd


PATH_HOME = Path.home()

PATH_DIR = Path(__file__).parents[4]

CARTELLA_OUTPUT = PATH_DIR / "SCRIPT" / "BUSINESS" / "01_FCST_Business" / "file_generati_last"
ERRORE = Fore.RED + "\nERRORE --> CONTROLLA IL CODICE E/O I FILE IN INGRESSO"

COL_NOMI = 0
COL_DATA_APPUNTAMENTO =  "Data appuntamento"
INIZIO_GARA = "01/01/2026"
INIZIO_GARA = pd.to_datetime(INIZIO_GARA, dayfirst=True)

#NOMI COLONNE PER FILTRARE AGENTE
COLONNA_AGENTE_GARA = "Proprietario (Ordine)"
COLONNA_AGENTE_OPP = "Proprietario (Opportunità)"
COLONNA_AGENTE_APP = "Azienda assegnata a " 

#TESTO DA VISUALIZZARE NEL FOLDER BROWSER
TESTO_CARTELLA = "SELEZIONA LA CARTELLA DI OGGI!!!"

#COLONNE PER FILTRAGGIO DF
COL_DATA_INSERIMENTO = "Data Inserimento OmniSales"
COL_DATA_ATTIVAZIONE = "Data Attivazione"

#PERCORSI FILE MASTER 
FILE_MASTER_GIORGIO = PATH_DIR / "SCRIPT" / "BUSINESS" / "01_FCST_Business" / "TEMPLATE" / "MASTER - GIORGIO.xlsx"
FILE_MASTER_VENDITORI = PATH_DIR / "SCRIPT" / "BUSINESS" / "01_FCST_Business" /  "TEMPLATE" / "MASTER.xlsx"

#LISTA NOMI PER FILTRAGGIO 
LISTA_NOMI = PATH_DIR / "SCRIPT" / "BUSINESS" / "01_FCST_Business" / "TEMPLATE" / "lista_nomi_gara.xlsx"

PATH_ONEDRIVE_FILE = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / ".parquet"

#DIZIONARI PER PERCORSI OneDrive
ONEDRIVE_VENDITORI = {
    "E.AGALLIU"     : PATH_HOME / "My Way S.r.l" / "BUSINESS - AGALLIU - Eduart Agalliu" / "AGENDA - PERFORMANCE",
    "A.MILANI"      : PATH_HOME / "My Way S.r.l" / "BUSINESS - MILANI - Alberto Milani" / "AGENDA - PERFORMANCE",
    "M.DEMELAS"     : PATH_HOME / "My Way S.r.l" / "BUSINESS - DEMELAS - Mario Demelas" / "AGENDA - PERFORMANCE",
    "G.MARRA"       : PATH_HOME / "My Way S.r.l" / "BUSINESS - MARRA - Giovanni Marra" / "AGENDA - PERFORMANCE",
    "D.CARUGO"      : PATH_HOME / "My Way S.r.l" / "BUSINESS - CARUGO - Danilo Carugo" / "AGENDA - PERFORMANCE",
    "D.GNANI"       : PATH_HOME / "My Way S.r.l" / "BUSINESS - GNANI - Doriano Gnani" / "AGENDA - PERFORMANCE",
    "E.PIGNATTA"    : PATH_HOME / "My Way S.r.l" / "BUSINESS - PIGNATTA - Enrico Pignatta" / "AGENDA - PERFORMANCE",
    "M.SALA"        : PATH_HOME / "My Way S.r.l" / "BUSINESS - SALA - Mauro Sala" / "AGENDA - PERFORMANCE",
    "R.SCIMONE"     : PATH_HOME / "My Way S.r.l" / "BUSINESS - SCIMONE - Riccardo Scimone" / "AGENDA - PERFORMANCE",
    "L.MATTAINI"    : PATH_HOME / "My Way S.r.l" / "BUSINESS - MATTAINI - Luca Mattaini" / "AGENDA - PERFORMANCE",
    "F.ARLOTTA"     : PATH_HOME / "My Way S.r.l" / "BUSINESS - ARLOTTA - Fabio Arlotta" / "AGENDA - PERFORMANCE",
}

COLONNE_CORRETTE = ['Cliente (Ordine)', 'Partita IVA (Ordine)', 'ID Pratica',
       'Prodotto esistente', 'Tipologia Servizio (Prodotto esistente)',
       'Quantità', 'Prezzo unitario', 'Importo totale', 'Data creazione',
       'Data Inserimento OmniSales', 'Data Passaggio ACA', 'Data Attivazione',
       'Proprietario (Ordine)', 'ID ordine (Ordine)', 'Motivo stato (Ordine)',
       'Valuta', 'Codice Aggregato', 'Famiglia', 'Squadra Energia',
       'scala sconti']

ONEDRIVE_GIORGIO = PATH_HOME / "My Way S.r.l" / "BUSINESS - MANDELLI - Giorgio Mandelli" / "BUSINESS" / "AGENDA - PERFORMANCE"


#FUNZIONE PER TROVARE E CONTROLLARE LA CARTELLA "RAW_FILE" su teams
#--------------------------------------------------------------
def trova_file(path_cartella):
    ESTENSIONI = ["*.parquet"]
    file_trovati = [f for ext in ESTENSIONI for f in path_cartella.glob(ext)]
 
    file_gara = None
    file_opportunita  = None
    file_appuntamenti = None

    for file in file_trovati:
        nome = file.name.lower()
        if "opportunit" in nome:
            file_opportunita = file
        elif "inflow" in nome:
            file_gara = file
        elif "appuntamenti" in nome:
            file_appuntamenti = file

    print(f"    📁 Gara:          {file_gara}")
    print(f"    📁 Opportunita:   {file_opportunita}")
    print(f"    📁 Appuntamenti:  {file_appuntamenti}\n")

    return file_gara, file_opportunita, file_appuntamenti


#FUNZIONE PER SVUOTARE UNA CARTELLA DA FILE 
#---------------------------------------------------------------------------
def svuota_cartella(cartella):
    for file in cartella.iterdir():
        if file.is_file():
            file.unlink()
            print(f"  🗑️ File eliminato da {cartella}: {file.name}")
    print(Fore.GREEN + f"\n  ✅ Cartella svuotata: {cartella.as_posix()}\n")

def elimina_file_da_cartella(file):
    if file.exists():
        file.unlink()
        tqdm.write(f"  ✅ file {file.name} è stato rimosso per far spazio al nuovo {file.name} ")
