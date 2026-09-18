from formatta_gara.AGGREGA_STORICO import main as gara
from formatta_opportunità.AGGREGA_STORICO import main as opportunita
from formatta_appuntamenti.AGGREGA_STORICO import main as appuntamenti
import sys
from config import (
    trova_file,
    PATH_RAW_FILE, PATH_STORICO_BASI_DATI
)

from colorama import Fore, Style, init
init(autoreset = True)

def main():
    
    # 1. formatta gara
    try:
        file_gara = trova_file(PATH_RAW_FILE, "Gara")
        file_gara_storico = trova_file(PATH_STORICO_BASI_DATI, "Storico gara")
        gara(file_gara, file_gara_storico)
    except Exception as e:
        print("[" + Fore.RED + "ERRORE" + Fore.RESET + f"] Formatta gara ha riscontrato un problema: {e}")
        sys.exit(1)
    # 2. formatta opportunità
    try:
        file_opportunita = trova_file(PATH_RAW_FILE, "Opportunita")
        file_opportunita_storico = trova_file(PATH_STORICO_BASI_DATI, "Storico opportunita")   
        opportunita(file_opportunita, file_opportunita_storico)
    except Exception as e:
        print("[" + Fore.RED + "ERRORE" + Fore.RESET + f"] Formatta opportunità ha riscontrato un problema: {e}")
        sys.exit(1)

    # 3. formatta appuntamenti
    try:
        file__appuntamenti_storico = trova_file(PATH_STORICO_BASI_DATI, "Storico Appuntamenti")
        file_appuntamenti = trova_file(PATH_RAW_FILE, "Appuntamenti")
        appuntamenti(file__appuntamenti_storico, file_appuntamenti)
    except Exception as e:
        print("[" + Fore.RED + "ERRORE" + Fore.RESET + f"] Formatta appuntamenti ha riscontrato un problema: {e}")

if __name__ == "__main__":
    main()