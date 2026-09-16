from pathlib import Path
from copy import copy
from colorama import Fore, init
init(autoreset = True)

PATH_HOME = Path.home()

#PERCORSI
CARTELLA_RAW_FILE = PATH_HOME / "My Way S.r.l" / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / "CAMPAGNA"


ONEDRIVE_VENDITORI = {
    "Agalliu Eduart"    : PATH_HOME / "My Way S.r.l" / "BUSINESS - AGALLIU - Eduart Agalliu" / "CAMPAGNE - DOCUMENTI",
    "Milani Alberto"    : PATH_HOME / "My Way S.r.l" / "BUSINESS - MILANI - Alberto Milani" / "CAMPAGNE - DOCUMENTI",
    "Demelas Mario"     : PATH_HOME / "My Way S.r.l" / "BUSINESS - DEMELAS - Mario Demelas" / "CAMPAGNE - DOCUMENTI",
    "Marra Giovanni"    : PATH_HOME / "My Way S.r.l" / "BUSINESS - MARRA - Giovanni Marra" / "CAMPAGNE - DOCUMENTI",
    "Carugo Danilo"     : PATH_HOME / "My Way S.r.l" / "BUSINESS - CARUGO - Danilo Carugo" / "CAMPAGNE - DOCUMENTI",
    "Gnani Doriano"     : PATH_HOME / "My Way S.r.l" / "BUSINESS - GNANI - Doriano Gnani" / "CAMPAGNE - DOCUMENTI",
    "Pignatta Enrico"   : PATH_HOME / "My Way S.r.l" / "BUSINESS - PIGNATTA - Enrico Pignatta" / "CAMPAGNE - DOCUMENTI",
    "Sala Mauro"        : PATH_HOME / "My Way S.r.l" / "BUSINESS - SALA - Mauro Sala" / "CAMPAGNE - DOCUMENTI",
    "Scimone Riccardo"  : PATH_HOME / "My Way S.r.l" / "BUSINESS - SCIMONE - Riccardo Scimone" / "CAMPAGNE - DOCUMENTI",
    "CRM My Way"        : [PATH_HOME / "My Way S.r.l" / "BUSINESS - MATTAINI - Luca Mattaini" / "CAMPAGNE - DOCUMENTI",
                            PATH_HOME / "My Way S.r.l" / "BUSINESS - FEBBO - Cinzia Febbo" / "CAMPAGNE - DOCUMENTI"],
    "Arlotta Fabio"     : PATH_HOME / "My Way S.r.l" / "BUSINESS - ARLOTTA - Fabio Arlotta" / "AGENDA - PERFORMANCE",
    "Mandelli Giorgio"  : PATH_HOME / "My Way S.r.l" / "BUSINESS - MANDELLI - Giorgio Mandelli" / "BUSINESS" / "CAMPAGNE - DOCUMENTI"
}

#FUNZIONI
def copia_stile_cella(cella_origine, cella_destinazione):
    """Copia lo stile da una cella all'altra."""
    if cella_origine.has_style:
        cella_destinazione.font = copy(cella_origine.font)
        cella_destinazione.border = copy(cella_origine.border)
        cella_destinazione.fill = copy(cella_origine.fill)
        cella_destinazione.number_format = copy(cella_origine.number_format)
        cella_destinazione.protection = copy(cella_origine.protection)
        cella_destinazione.alignment = copy(cella_origine.alignment)
        
def trova_file_campagna(agente, destinazioni):

    if not isinstance(destinazioni, list):
            destinazioni = [destinazioni]
            
    for path in destinazioni:
        for file in path.glob(f"*CAMPAGNA_{agente}*"):
            #in questo caso prende 1 volta il file CRM perchè lo va a riassegnare al secondo ciclo 
            file_path = file 
    
    return file_path

def trova_cartella_campagna(cartella_base):
    
    sottocartelle = sorted(
        cartella_base.iterdir(),
        key=lambda p: int(p.name[:2])
    )
    
    cartella_corretta = sottocartelle[-1]

    return cartella_corretta / "CAMPAGNE COMPILATE"