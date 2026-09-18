from pathlib import Path
from datetime import datetime
import os

PATH_HOME = Path.home()

PATH_DIR = Path(__file__).parents[4]

PATH_TEMPLATE = PATH_DIR / "SCRIPT" / "BUSINESS" / "02_(OLD)_APPUNTAMENTI_SETTIMANA" / "TEMPLATE" / "TEMPLATE.xlsx"
PATH_PARQUET = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / ".parquet"

# VARIABILE SETTIMANA CORRENTE
oggi = datetime.today()
SETTIMANA_CORRENTE = oggi.isocalendar().week

#COLONNE APPUNTAMENTI 
COLONNE_APPUNTAMENTI = ['Regione sociale', 'Data appuntamento', "SETTIMANA", 'Tipo appuntamento', 'Azienda assegnata a ', 'Esito Appuntamento', 'Note Appuntamento']

#DATA SU CUI FILTRARE DF
DATA_FILTRO = "01/01/2026"

#FUNZIONE PER TROVARE E CONTROLLARE LA CARTELLA "RAW_FILE"
#--------------------------------------------------------------
def trova_raw_file(path_cartella):
    ESTENSIONI = ["*.parquet"]
    file_trovati = [file for ext in ESTENSIONI for file in path_cartella.glob(ext)]

    appuntamenti = None

    for file in file_trovati:
        
        nome = file.name.lower()
        if "appuntamenti" in nome:
            appuntamenti = file
            
    return appuntamenti


#LISTA VENDITORI PER CICLO 
VENDITORI = ["L.MATTAINI", "R.SCIMONE", "M.DEMELAS", 'E.PIGNATTA', 'A.MILANI', 'G.MARRA', 'D.CARUGO', 'M.SALA', 'E.AGALLIU', 'D.GNANI', 'G.PASQUALETTI', 'R.TUNESI', "G.MANDELLI"]

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
    "G.MANDELLI"    : PATH_HOME / "My Way S.r.l" / "BUSINESS - MANDELLI - Giorgio Mandelli" / "BUSINESS" / "AGENDA - PERFORMANCE"
}
