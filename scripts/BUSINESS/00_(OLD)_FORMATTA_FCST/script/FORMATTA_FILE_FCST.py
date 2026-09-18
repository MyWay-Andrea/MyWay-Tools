import logging
import sys
import shutil

#IMPORTAZIONE FILE:
#----------------------------------------------------------------------
from config import copia_in_onedrive, PERCORSO_TEAMS, PATH_RAW_FILE, trova_raw_file, elimina_file_da_cartella, svuota_cartella, PATH_DIR, cartella_output, PATH_PARQUET
from formatta_gara import main as formatta_gara
from formatta_opportunita import main as formatta_opportunita
from formatta_appuntamenti import main as formatta_appuntamenti

from colorama import Fore, Style, init
init(autoreset=True) # Resetta il colore automaticamente dopo ogni print

#PER GARANTIRE AGGIORNAMENTO RAPIDO A CONSOLE MENU
import functools, builtins
builtins.print = functools.partial(print, flush=True)

LOG_PATH = PATH_DIR / "SCRIPT" / "BUSINESS" / "00_FORMATTA_FCST" / "FORMATTAZIONE_log.log"
LOG_PATH_ONEDRIVE = PERCORSO_TEAMS / "FORMATTAZIONE_log.log"

# Configura il logger: file, formato data/ora e livello di dettaglio
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8', mode='w'), #mode = "w" sovrascrive ogni volta il file
    ]
)

def esegui_step(funzione, file, nome_step):
    try:
        risultato = funzione(file)
        logging.info(f'  ✅ "{file.name}" elaborato correttamente')
        return risultato
    except Exception as e:
        logging.error(f'  ❌ ERRORE in {nome_step}: {e}')
        sys.exit(1)


def main():
    logging.info('---------------------------------------------------------')
    logging.info('"PARTENZA SCRIPT "FORMATTA FILE"...')
    logging.info('---------------------------------------------------------')

    svuota_cartella(cartella_output)
    print("CERCA FILE")
    file_gara, file_opportunita, file_appuntamenti = trova_raw_file(PATH_RAW_FILE)
    print("FILE TROVATI")

    
    
    try:
        file_gara_OK, df_gara = formatta_gara(file_gara)
        if file_gara_OK is None or df_gara.empty:
            print("[" + Fore.RED + "ERRORE" + Fore.RESET + "] nella formattazione del file 'formatta_gara'")

        file_opportunita_OK, df_opportunita = formatta_opportunita(file_opportunita)
        if file_opportunita_OK is None or df_opportunita.empty:
            print("[" + Fore.RED + "ERRORE" + Fore.RESET + "] nella formattazione del file 'formatta_opportunita'")

        file_appuntamenti_OK, df_appuntamenti = formatta_appuntamenti(file_appuntamenti)
        if file_appuntamenti_OK is None or  df_appuntamenti.empty:
            print("[" + Fore.RED + "ERRORE" + Fore.RESET + "] nella formattazione del file 'formatta_appuntamenti'")
    except Exception as e:
        print(f"Si è verificato un errore... --> {str(e)}")

    lista_file = [file_gara_OK, file_opportunita_OK, file_appuntamenti_OK]

    dict_df = {
        "Gara (inflow)" : df_gara,
        "Opportunità" : df_opportunita,
        "Appuntamenti" : df_appuntamenti
    }

    # fuori dal loop - copia i parquet una volta sola
    copia_in_onedrive(dict_df, PATH_PARQUET)
    print(Fore.GREEN + "\n ✅ SALVATAGGIO PARQUET AVVENUTO CON " + Fore.GREEN + Style.BRIGHT + "SUCCESSO")
    # nel loop - copia solo i file excel
    for file in lista_file:
        try:
            copia_in_onedrive(file, PERCORSO_TEAMS)
            
        except Exception as e:
            logging.error(f"  ❌ TEAMS --> ERRORE nel caricamento del file {file}")
            
    print(Fore.GREEN + "\n ✅ SALVATAGGIO SU TEAMS AVVENUTO CON " + Fore.GREEN + Style.BRIGHT + "SUCCESSO")
    print("\nCARICAMENTO FILE SU " + Fore.BLUE + " TEAMS " + Fore.RESET + "AVVENUTO CON SUCCESSO")
    #elimina file da cartella (non svuota tutta la cartella)
    elimina_file_da_cartella(file_gara, file_opportunita, file_appuntamenti)


if __name__ == "__main__":
    try:
        main()

        #CHIUSURA FILE LOG
        print(Fore.YELLOW + "\n ✅ SCRIPT ESEGUITO CON SUCCESSO")

        #chiudi il sistema di logging 
        logging.shutdown()

        #copia il file .log su Teams
        shutil.copy2(LOG_PATH, LOG_PATH_ONEDRIVE)
        print("Log aggiornato su OneDrive.")
        
    except Exception as e:
        try:
            shutil.copy2(LOG_PATH, LOG_PATH_ONEDRIVE)
        except:
            pass
        
        print(Fore.RED + f"\n  ❌ ERRORE premi invio per chiudere la finestra e controlla il codice.... {e}")