from pathlib import Path
import sys 
from colorama import Fore, init
init(autoreset = True)
#collegamento a file common.negozi.py per estraizone automatica 
#=============================================================#

#salva con path assoluto il path della cartella consumer
CARTELLA_CONSUMER = Path(__file__).resolve().parents[1]

PATH_SHAREPOINT  = Path.home() / "My Way S.r.l"

#da la possibilità a python di trovare la cartella 
if str(CARTELLA_CONSUMER) not in sys.path:
    sys.path.insert(0, str(CARTELLA_CONSUMER))

#importa la funzione carica negozi 
from common.negozi import trova_cartelle_negozi

#=============================================================#



def trova_file(cartele_negozi:dict[str, Path]) -> list[Path]:

    file_digi = {}
 
    for negozio, cartella in cartele_negozi.items():

        file_trovato = None

        percorso_file = cartella / "TRACCIAMENTO" / f"DIGI_{negozio}.xlsx"

        if percorso_file.is_file():
            file_trovato = percorso_file

        if file_trovato:  
            file_digi[negozio] = file_trovato            
        else:
            print(Fore.RED + " ✕ " + Fore.RESET + f"{negozio} - non è stato trovato il file")
        
    return file_digi

CARTELLE_NEGOZI = trova_cartelle_negozi()
FILE_DIGI = trova_file(CARTELLE_NEGOZI)

