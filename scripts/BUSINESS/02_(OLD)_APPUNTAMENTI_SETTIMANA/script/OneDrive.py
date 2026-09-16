from pathlib import Path
import shutil
from colorama import Fore, init
init(autoreset=True)

def copia_in_onedrive(file_agente, percorsi, agente):
    try:
        cartella_dest = percorsi[agente]
    except Exception as e:
        print(f" {agente} non presente su "+Fore.BLUE+"Teams")
        return
    
    file_agente = Path(file_agente)
    file_dest = cartella_dest / file_agente.name
    print(file_dest)
    shutil.copy2(file_agente, file_dest)

    print(" Caricamento su "+Fore.BLUE+"Teams"+Fore.RESET+" avventuo con successo!")

    return file_dest