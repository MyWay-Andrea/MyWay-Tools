from config import trova_file, run_silenzioso, PATH_RAW_FILES

from formatta_magazzino.FORMATTA_MAGAZZINO import main as formatta_magazzino
from formatta_pedonalita.FORMATTA_PEDONALITA import main as formatta_pedonalita

from colorama import Fore, init
init(autoreset=True)
def main(path_magazzino, path_pedonalita):
        
    steps = {
        "Formatta magazzino":  (formatta_magazzino,  path_magazzino),  
        "Formatta pedonalita": (formatta_pedonalita, path_pedonalita),
    }
    for descrizione, (funzione, path) in steps.items(): 
        try:
            print("Elaboro: " + Fore.YELLOW + f"{descrizione}... ⏳")
            run_silenzioso(funzione, path)               
            print(f"✅ {descrizione} eseguita con successo\n")
        except Exception as e:
            print(f"❌ ERRORE --> {e}")
                 
if __name__ == "__main__":
    #importa path dei file 
    path_magazzino = trova_file(PATH_RAW_FILES, "magazzino")
    path_pedonalita = trova_file(PATH_RAW_FILES, "pedonalita")
    #path_performance = trova_file(PATH_RAW_FILES, "performance")

    main(path_magazzino, path_pedonalita)   