from pathlib import Path
import json
import sys 
from colorama import Fore, init
init(autoreset=True)
PATH_DIR = Path(__file__).parents[1]

PATH_VENDITORI = PATH_DIR.resolve() / "config" / "venditori.json"



def leggi_venditori() -> list[dict]:
    ''' Funzione riutilizzabile da tutti gli script per leggere il file "venditori.json"  '''

    with PATH_VENDITORI.open("r", encoding="utf-8") as file:
        dati = json.load(file)

        venditori = dati.get("venditori")

        if not isinstance(venditori, list):
            raise ValueError(
                f"La chiave 'venditori' in {PATH_VENDITORI} deve contenere una lista"
            )
        
        for venditore in venditori:
            if not isinstance(venditore, dict):
                raise ValueError("Ogni venditore deve essere un dizionario")

            if not venditore.get("nome_crm"):
                raise ValueError("Ogni venditore deve avere il campo 'nome_crm'")

            if not isinstance(venditore.get("alias_cb"), list):
                raise ValueError(
                    f"Il venditore {venditore['nome_crm']} deve avere una lista 'alias_cb'"
                )

        return venditori



def trova_lista_file(path) -> list[Path]:
    '''Restituisce una lista di file presenti in una determinata cartella'''
    if not path.exists():
        print(Fore.RED + " ✕ " + Fore.RESET + f" Il percorso {path} non esiste...")
        sys.exit(1)

    files = []
    for ext in [".parquet", ".json", ".csv", ".xls", ".xlsx"]:
        files.extend(path.glob(f"*{ext}"))

    if not files:
        print(Fore.RED + " ✕ " + Fore.RESET + f"La cartella {path} non ha restituito alcun file...")
        sys.exit(1)

    print(Fore.CYAN + f" ℹ File trovati: {len(files)}")
    for file in files:
        print(Fore.LIGHTBLACK_EX + f"   • {file.name}")

    return files


