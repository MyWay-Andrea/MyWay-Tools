#FILE CON TUTTE LE VARIABILI GLOBALI 
from pathlib import Path
from copy import copy
import shutil
import pandas as pd
import sys
import time

from colorama import Fore, Style, init
init(autoreset=True) # Resetta il colore automaticamente dopo ogni print

import logging

PATH_HOME = Path.home()

PATH_DIR = Path(__file__).parents[4]

ERRORE = Fore.RED + "\nERRORE --> controlla file log per ulteriori informazioni"

cartella_output =  PATH_DIR / "SCRIPT" / "BUSINESS" / "00_FORMATTA_FCST" / "file_generati_last"

#FORMATTA GARA
#------------------------------------------------------------------
COLONNE = [0,1,2,3,4,5,6,17,8,9,10,11,12,13,14,15,16]
SERVIZI_DA_SCONTARE = ["SIM VOCE", "SIM DATI", "VRU INTERNO"]
COLONNA_AGENTE_GARA = "Proprietario (Ordine)"
MASTER_GARA = PATH_DIR / "SCRIPT" / "BUSINESS" / "00_FORMATTA_FCST" / "template" / "TEMPLATE_GARA.xlsx"
DATE_COLS = [8, 9, 10, 11]
DATE_COLS_NAME = ['Ordini di vendita Orario creazione', 'Items D.I.B.S.', 'Items D.P.A.', 'Items D.A.']
SHEET_GARA = "GARA"
#------------------------------------------------------------------


#FORMATTA OPPORTUNITà
#------------------------------------------------------------------
FILTRO_STATO = ["Aperta"]
LISTA_COLONNE_OPPORTUNITA = [2, 4, 10, 17, 12, 9, 19, 27, 28, 29, 6, 5]
COLONNA_AGENTE_OPP = "Proprietario (Opportunità)"
MASTER_OPPORTUNITA = PATH_DIR / "SCRIPT" / "BUSINESS" / "00_FORMATTA_FCST" / "template" / "TEMPLATE_OPPORTUNITA.xlsx"
SHEET_OPPORTUNITA = "OPPORTUNITA"
DATE_COLS_NAME_OPP = [' "Data Chiusura Prevista"', ' "Orario modifica"', ' "Orario creazione"']
#------------------------------------------------------------------


#FORMATTA APPUNTAMENTI
#------------------------------------------------------------------
filtro_appuntamento = ["CB", "Autoprocurato CB"]
COLONNA_DATA = ' "Orario e data inizio"'
DATA_INIZIO = pd.Timestamp('2026-01-01')
COLONNA_AGENTE_APP = "Calendario Assegnato a "
MASTER_APPUNTAMENTI = PATH_DIR / "SCRIPT" / "BUSINESS" / "00_FORMATTA_FCST" / "template" / "TEMPLATE_APPUNTAMENTI.xlsx"
SHEET_APPUNTAMENTI = "APPUNTAMENTI"
#------------------------------------------------------------------

#FILE FORMATTA_FILE
#--------------------------------------------------------
PATH_RAW_FILE = PATH_DIR / "SCRIPT" / "00_RAW_FILE" 

#COPIA FORMATTAZIONE CELLE 
#--------------------------------------------------------
def copia_formattaz_cella(cella_input, cella_output):
    if cella_input.has_style:
        cella_output.font = copy(cella_input.font)
        cella_output.border = copy(cella_input.border)
        cella_output.fill = copy(cella_input.fill)
        cella_output.number_format = copy(cella_input.number_format)
        cella_output.protection = copy(cella_input.protection)
        cella_output.alignment = copy(cella_input.alignment)



#COPIA TEMPLATE 
#----------------------------------------------------
def copia_template(file_master, file = None, nome = None):
    if file:
        file_output = cartella_output / f"{file.name}"
    elif nome:
        file_output = cartella_output / nome
    else:
        print(Fore.RED + " ❌   MANCANZA DI NOME E/O PERCORSO")
    shutil.copy(file_master, file_output)

    return file_output 



#COPIA IL IL FILE SULLA CARTELLA SINCRONIZZATA DI TEAMS (SIA EXCEL CHE .parquet)
#----------------------------------------------------
def copia_in_onedrive(file_agente, percorsi, agente=None):
    if isinstance(percorsi, dict):
        cartella_dest = percorsi[agente]
    else:
        cartella_dest = percorsi     
        
    if isinstance(file_agente, dict):  
        for nome, df in file_agente.items():
            try:
                cartella_dest.mkdir(parents=True, exist_ok=True)
                df.to_parquet(cartella_dest / f"{nome}.parquet", index=False)  
                logging.info(f"  ✅ File: {nome} salvato in formato '.parquet'")
            except Exception as e:
                logging.error(f"  ❌ ERRORE parquet {nome} --> {e}")
    else:
        file_dest = cartella_dest / Path(file_agente).name
        shutil.copy2(file_agente, file_dest)
        logging.info(f"  ✅ TEAMS --> caricamento {file_dest.name} avvenuto con successo")

PATH_PARQUET = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / ".parquet"
PERCORSO_TEAMS = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / "BASI_DATI_xlsx"

#FUNZIONE PER TROVARE E CONTROLLARE LA CARTELLA "RAW_FILE"
#--------------------------------------------------------------
def trova_raw_file(path_cartella):
    ESTENSIONI = ["*.xlsx", "*.xlsm", "*.xls", "*.csv"]
    file_trovati = [f for ext in ESTENSIONI for f in path_cartella.glob(ext)]
 
    file_gara = None
    file_opportunita  = None
    file_appuntamenti = None

    for file in file_trovati:
        logging.info(f"  ⚠️ file trovati: {file} ")
        nome = file.name.lower()
        if "opportunit" in nome:
            file_opportunita = file
            try:
                file_opportunita = file_opportunita.rename(file_opportunita.parent / "Opportunità.csv")
                logging.info(f"  🖊️ Rinomina {file_opportunita.name} andata a BUON fine") 
            except Exception as e:
                logging.warning(f"  ⚠️ Rinomina {file_opportunita.name} ha causato un errore")
                print(ERRORE)
                
        elif "inflow" in nome:
            file_gara = file
            try:
                file_gara = file_gara.rename(file_gara.parent / "Gara (Inflow).xlsx")
                logging.info(f"  🖊️ Rinomina {file_gara.name} andata a BUON fine") 
            except Exception as e:
                logging.warning(f"  ⚠️ Rinomina {file_gara.name} ha causato un errore")
                print(ERRORE)

        elif "calendario" in nome:
            file_appuntamenti = file
            try:
                file_appuntamenti = file_appuntamenti.rename(file_appuntamenti.parent / "Appuntamenti.csv")
                logging.info(f"  🖊️ Rinomina {file_appuntamenti.name} andata a BUON fine")
            except Exception as e:
                logging.warning(f"  ⚠️ Rinomina {file_appuntamenti.name} ha causato un errore")
                print(ERRORE)

    check = {
    "Inflow (Gara)": file_gara,
    "Opportunità": file_opportunita,
    "Calendario (Appuntamenti)": file_appuntamenti
    }

    MANCANTI = [file for file, contenuto in check.items() if contenuto is None]

    # Invece di questo doppio controllo, basta:
    if MANCANTI:
        logging.error(f"  ❌ File mancanti: {MANCANTI} in {path_cartella}")
        print(ERRORE)
        sys.exit(1)

    logging.info(f"  ✅ File importati con successo da: {path_cartella.as_posix()}")
    return file_gara, file_opportunita, file_appuntamenti



#FUNZIONE PER SVUOTARE UNA CARTELLA DA FILE 
#---------------------------------------------------------------------------
def svuota_cartella(cartella):
    for file in cartella.iterdir():
        if file.is_file():
            file.unlink()
            logging.info(f"  🗑️ File eliminato da {cartella}: {file.name}")
    logging.info(f"  ✅ Cartella svuotata: {cartella.as_posix()}")


#FUNZIONE PER ELIMIANRE FILE USATI DALLO SCRIPT
#----------------------------------------------------------------------------
def elimina_file_da_cartella(*files):
    for file in files:
        file = Path(file)
        if file.exists() and file.is_file():
            file.unlink()
            time.sleep(1)
            if file.exists():
                print(f" ❌ file: {file.name} non è stato cancellato corretamente ")
            

def forza_formato_excel(ws):
    for row in range(2, ws.max_row + 1):

        #FORZA COLONNA DATE
        ws.cell(row=row, column= 9).number_format = 'DD/MM/YYYY'
        ws.cell(row=row, column= 10).number_format = 'DD/MM/YYYY'
        ws.cell(row=row, column= 11).number_format = 'DD/MM/YYYY'
        ws.cell(row=row, column= 12).number_format = 'DD/MM/YYYY'

        #FORZA COLONNE VALUTA
        ws.cell(row=row, column= 7).number_format = '#,##0.00 €'
        ws.cell(row=row, column= 8).number_format = '#,##0.00 €'
