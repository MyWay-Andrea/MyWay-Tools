import pandas as pd
from pathlib import Path
import sys
from colorama import Fore, Style, init
init(autoreset=True)
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font

# PERCORSI
PATH_HOME           = Path.home()
PATH_DIR            = Path(__file__).parents[3]

#path input
PATH_RAW_FILE = PATH_DIR / "SCRIPT" / "00_RAW_FILE"

#path output
PERCORSO_TEAMS         = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI"
PATH_PARQUET           = PERCORSO_TEAMS / ".parquet"
PATH_BASI_DATI         = PERCORSO_TEAMS / "BASI_DATI_xlsx"
PATH_STORICO_BASI_DATI = PATH_BASI_DATI / "STORICO"

#COVERSIONE NOMI
CONVERSIONE_NOMI = {
    "Giorgio Mandelli"  : "G.MANDELLI",
    "Giovanni Marra"    : "G.MARRA",
    "Eduart Agalliu"    : "E.AGALLIU",
    "Alberto Milani"    : "A.MILANI",
    "Danilo Carugo"     : "D.CARUGO",
    "Doriano Gnani"     : "D.GNANI",
    "Enrico Pignatta"   : "E.PIGNATTA",
    "Mauro Sala"        : "M.SALA",
    "Riccardo Scimone"  : "R.SCIMONE",
    "Fabio Arlotta"     : "F.ARLOTTA",
    "CRM MWR"           : "CRM My Way"
}

COLONNE_APPUNTAMENTI = [
     'Data', "Orario", 'Cliente', 'In carico a', 
     'Accompagnato da', 'Indirizzo', 'Fatta/da fare', 
     'Tipo di appuntamento', 'Nota interna',   
     ]

#FUNZIONI

#trova file da elaborare
def trova_file(path_cartella, parametro):
    ESTENSIONI = ["*.xlsx", "*.xlsm", "*.xls", "*.parquet", "*.csv"]
    file_trovati = [f for ext in ESTENSIONI for f in path_cartella.glob(ext)]
    file_chose = None
    for file in file_trovati:
        if parametro == "Appuntamenti":
            if "appuntamenti" in file.name.lower():
                    file_chose = file
        elif parametro == "Storico":
            if "storico appuntamenti" in file.name.lower():
                    file_chose = file
                    
    if file_chose is None:
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Nessun file che rispetti il parametro: {parametro}")
        sys.exit(1)

    return file_chose


#formatta file excel
def _formatta_excel(path: str):
    '''
    Funzione che serve per dare un pò di colore al file finale, e per dare il giusto formato 
    alle date ai prezzi.
    Si usano i set al posto delle liste perchè sono più veloci ed evitano di dover ciclare tutto il file 
    per trovare le colonne su cui applicare la formattazione.
    '''
    col_date    = set()

    wb = load_workbook(path)
    ws = wb.active

    # Colori
    fill_blu            = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    fill_giallo         = PatternFill(start_color="FFD966", end_color="FFD966", fill_type="solid")
    fill_rosso          = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    font_bianco         = Font(color="FFFFFF", bold=True)
    font_nero           = Font(color="000000", bold=True)
    font_verde_testo    = Font(color="2FBF47", bold = True)
    font_arancione_testo= Font(color="EA6B14", bold = True)
    font_rosso_testo    = Font(color="FF0000", bold = True)
    font_azzurro_testo  = Font(color="00B0F0", bold = True)
    
    for cell in ws[1]:  # prima riga = intestazioni
        col_name = str(cell.value).strip().lower() if cell.value else ""

        if "in carico a" in col_name:
            cell.fill = fill_giallo
            cell.font = font_nero
        elif "probabilit" in col_name:
            cell.fill = fill_rosso
            cell.font = font_bianco
        else:
            cell.fill = fill_blu
            cell.font = font_bianco
        
        #crea lista di colonne data e prezzo/importo
        if "data" in col_name:
            col_date.add(cell.column)

    #Formatta Date, Prezzi e colori dell stato ordine
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            if cell.column in col_date:
                cell.number_format = "DD/MM/YYYY"
            elif str(cell.value).strip().lower() == "attività fatta":
                cell.font = font_verde_testo
            elif str(cell.value).strip().lower() == "attività da fare":   
                cell.font = font_azzurro_testo
            elif str(cell.value).strip().lower() == "annullata":
                cell.font = font_rosso_testo
    wb.save(path)   

#carica i file sulla cartella ".parquet", "BASI_DATI_xlsx"
def carica_su_teams(df, *args: Path) -> None:
    '''
    Funzione dinamica di caricamento file su Teams, permette di essere utilizzata sia per caricare i
    file della gara corrente, sia quelli dello storico, riconoscendo in automatico i path inseriti
    e smistando i file nelle cartelle corrette
    '''
    try:
        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                f"Atteso pandas.DataFrame, ricevuto {type(df).__name__}"
            )   
        
        for path in args:

            #FILE GARA
            if ".parquet" in path.name:
                filename = path / "Appuntamenti.parquet"
                df.to_parquet(filename, index = False)

            elif "BASI_DATI_xlsx" in path.name:
                filename = path / "Appuntamenti.xlsx"
                df.to_excel(filename, index = False, engine = "openpyxl")
                _formatta_excel(filename)

            #FILE STORICO
            elif ".parquet" in path.parent.name and "STORICO" in path.name:
                filename = path / "Storico Appuntamenti.parquet"
                df.to_parquet(filename, index = False)

            elif "BASI_DATI_xlsx" in path.parent.name and "STORICO" in path.name:
                filename = path / "Storico Appuntamenti.xlsx"
                df.to_excel(filename, index = False, engine = "openpyxl")
                _formatta_excel(filename)

        print(Fore.GREEN + "✅ Caricamento su Teams avvenuto con successo\n")     

    except Exception as e:
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Caricamento file su Temas fallito --> {e}")

#elini file da cartella 
def elimina_file(file_path: Path) -> None:
    if file_path.is_file:
        file_path.unlink()
