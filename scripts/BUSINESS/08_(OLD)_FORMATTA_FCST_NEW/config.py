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
DEST                   = PATH_DIR / "SCRIPT" / "BUSINESS" / "03_FORMATTA_GARA" / "file_generati_last"
PERCORSO_TEAMS         = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI"
PATH_PARQUET           = PERCORSO_TEAMS / ".parquet"
PATH_BASI_DATI         = PERCORSO_TEAMS / "BASI_DATI_xlsx"
PATH_STORICO_PARQUET   = PATH_PARQUET / "STORICO"
PATH_STORICO_BASI_DATI = PATH_BASI_DATI / "STORICO"

#CONVERSIONE NOMI
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

COLONNE_CORRETTE_GARA   = ['Cliente (Ordine)', 'Partita IVA (Ordine)', 'ID Pratica',
       'Stato Ordine', 'Prodotto esistente', 'Tipologia Servizio (Prodotto esistente)',
       'Quantità', 'Prezzo unitario', 'Importo totale', 'Data creazione',
       'Data Inserimento OmniSales', 'Data Passaggio ACA', 'Data Attivazione',
       'Proprietario (Ordine)', 'ID ordine (Ordine)', 'Motivo stato (Ordine)',
       'Valuta', 'scala sconti']

COLONNE_CORRETTE_STORICO = ['Cliente (Ordine)', 'Partita IVA (Ordine)', 'ID Pratica',
       'Prodotto esistente', 'Tipologia Servizio (Prodotto esistente)',
       'Quantità', 'Prezzo unitario', 'Importo totale', 'Data creazione',
       'Data Inserimento OmniSales', 'Data Passaggio ACA', 'Data Attivazione',
       'Proprietario (Ordine)', 'ID ordine (Ordine)', 'Motivo stato (Ordine)',
       'Valuta', 'scala sconti']

COLONNE_OPPORTUNITA = [
    "Codice Opportunità", "Potenziale cliente (Opportunità)", "Partita IVA (Opportunità)", 
    "Proprietario (Opportunità)", "Stato (Opportunità)", "Data creazione", 
    "Data chiusura prev. (Opportunità)", "Data modifica", "Tipologia Servizio", "Prodotto esistente", 
    "Quantità", "Prezzo", "Importo totale", "Probabilità (Opportunità)"]

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
    param = parametro.strip().lower()

    for file in file_trovati:
        nome_file = file.name.lower()
        
        if param == "gara" and "gara_inflow" in nome_file:
            return file
        elif param == "opportunita" and "opportunita" in nome_file:
            return file
        elif param == "appuntamenti" and "appuntamenti" in nome_file:
            return file
        elif param == "storico gara" and "storico gara" in nome_file:
            return file
        elif param == "storico opportunita" and "storico opportunita" in nome_file:
            return file
        elif param == "storico appuntamenti" and "storico appuntamenti" in nome_file:
            return file

    print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Nessun file che rispetti il parametro: {parametro}")
    sys.exit(1)

#formatta file excel
def _formatta_excel(path: str):
    '''
    Funzione che serve per dare un pò di colore al file finale, e per dare il giusto formato 
    alle date ai prezzi.
    Si usano i set al posto delle liste perchè sono più veloci ed evitano di dover ciclare tutto il file 
    per trovare le colonne su cui applicare la formattazione.
    '''
    col_prezzi  = set()
    col_date    = set()
    col_prob    = set()
    
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

        if "proprietario" in col_name:
            cell.fill = fill_giallo
            cell.font = font_nero
        elif "scala sconti" in col_name or "sconto" in col_name:
            cell.fill = fill_rosso
            cell.font = font_bianco
        else:
            cell.fill = fill_blu
            cell.font = font_bianco

        #crea lista di colonne data, prezzo/importo e probabilità
        if "prezzo" in col_name or "importo" in col_name:
            col_prezzi.add(cell.column) 
        
        elif "data" in col_name:
            col_date.add(cell.column)

        elif "probabilit" in col_name:
            col_prob.add(cell.column)

    #Formatta Date, Prezzi e colori dell stato ordine
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            valore_cella = str(cell.value).strip().lower()
            if cell.column in col_date:
                cell.number_format = "DD/MM/YYYY"
            elif cell.column in col_prezzi:
                cell.number_format = "#,##0.00 €"
            elif cell.column in col_prob:
                cell.number_format = r"0\%"
            #sia per il file gara che per opportunita
            
            elif valore_cella == "attivato" or valore_cella == "aperta" or valore_cella == "attività fatta":
                cell.font = font_verde_testo
            elif valore_cella == "da inserire"or valore_cella == "acquisita" or valore_cella == "attività da fare":   
                cell.font = font_azzurro_testo
            elif valore_cella == "in attivazione":
                cell.font = font_arancione_testo
            elif valore_cella == "annullato"or valore_cella == "persa" or valore_cella == "annullata":
                cell.font = font_rosso_testo
            
    wb.save(path)   

#carica i file sulla cartella ".parquet", "BASI_DATI_xlsx"
def carica_su_teams(df, nome_file,  *args: Path) -> None:
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
                filename = path / f"{nome_file}.parquet"
                df.to_parquet(filename, index = False)

            elif "BASI_DATI_xlsx" in path.name:
                filename = path / f"{nome_file}.xlsx"
                df.to_excel(filename, index = False, engine = "openpyxl")
                _formatta_excel(filename)

            #FILE STORICO
            elif ".parquet" in path.parent.name and "STORICO" in path.name:
                filename = path / f"{nome_file}.parquet"
                df.to_parquet(filename, index = False)

            elif "BASI_DATI_xlsx" in path.parent.name and "STORICO" in path.name:
                filename = path / f"{nome_file}.xlsx"
                df.to_excel(filename, index = False, engine = "openpyxl")
                _formatta_excel(filename)

        print(Fore.GREEN + "✅ Caricamento su Teams avvenuto con successo\n")        
    except Exception as e:
        print("["+Fore.RED+"ERRORE"+Fore.RESET+f"] Caricamento file su Temas fallito --> {e}")
        sys.exit(1)
        
#elini file da cartella 
def elimina_file(file_path: Path) -> None:
    if file_path.is_file:
        file_path.unlink()