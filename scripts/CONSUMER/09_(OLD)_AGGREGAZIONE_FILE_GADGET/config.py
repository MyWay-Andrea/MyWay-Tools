import sys
from pathlib import Path
from colorama import Fore, init
init(autoreset = True)


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

'''

LOGICA:
1- trova nomi negozi
2- trova cartelle negozi partendo dai nomi
3- trova file GADGET uan volta che hai trovato le cartelle 
4- estrai df dai file e aggregali in un unico df
5- formatta le colonne
6- crea il file xlsx
7- carica su sharepoint 

'''
        
def trova_file_gadget(cartelle_negozi:dict[str, Path]) -> dict[str, Path]:
    
    file_gadget = {}

    for negozio, cartella in cartelle_negozi.items():

        file_trovato = None

        for ext in ["xlsx", "xls"]:
            percorso_file = cartella / "TRACCIAMENTO" / f"GADGET_{negozio}.{ext}"

            if percorso_file.is_file():
                file_trovato = percorso_file
                break

        if file_trovato:
            file_gadget[negozio] = file_trovato
        else:
            print(Fore.RED + f"✕ File GADGET non trovato per {negozio}")

    return file_gadget


CARTELLE_NEGOZI = trova_cartelle_negozi()
FILE_GADGET = trova_file_gadget(CARTELLE_NEGOZI)

COLONNE_DF = ["NEGOZIO", "DATA", "VENDITORE", "NOME CLIENTE", "COGNOME CLIENTE", "ACQUISTO - ATTIVAZIONE", "DESCRIZIONE"]
