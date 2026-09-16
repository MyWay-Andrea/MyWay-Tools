from colorama import Fore, init
init(autoreset = True)
from copy import copy
from pathlib import Path
import re
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

ONEDRIVE_CRM_SCAMBIO_DOCUMENTI = PATH_HOME / "My Way S.r.l" / "BUSINESS - CRM - CRM" / "SCAMBIO_DOCUMENTI"

# Tipologie da includere nell'aggregazione
TIPOLOGIE_INCLUSE = {"evo voce", "reward"}

def copia_stile_cella(cella_origine, cella_destinazione):
    """Copia lo stile da una cella all'altra."""
    if cella_origine.has_style:
        cella_destinazione.font = copy(cella_origine.font)
        cella_destinazione.border = copy(cella_origine.border)
        cella_destinazione.fill = copy(cella_origine.fill)
        cella_destinazione.number_format = copy(cella_origine.number_format)
        cella_destinazione.protection = copy(cella_origine.protection)
        cella_destinazione.alignment = copy(cella_origine.alignment)


def applica_logica_assegnata(df, col_agente='AGENTE'):
    """
    Se la colonna 0 (prima colonna) è 'si' → lascia col_agente invariato.
    Se la colonna 0 è 'no' → imposta col_agente = 'CRM My Way'.
    """
    if df.empty:
        return df
    prima_colonna = df.columns[0]
    if col_agente not in df.columns:
        print(Fore.YELLOW + f"  ⚠ Colonna '{col_agente}' non trovata, salto la logica assegnazione.")
        return df
    col0_normalizzata = df[prima_colonna].astype(str).str.strip().str.lower()
    mask_no = col0_normalizzata == 'no'
    df.loc[mask_no, col_agente] = 'CRM My Way'
    return df


def trova_raw_file(path_cartella):
    ESTENSIONI = ["*.xlsx"]
    '''
    ordina le cartella filtrandole per il numero davatni al nome
    in modo tale da prendere sempre quella più recente
    '''
    sottocartelle = sorted(
        path_cartella.iterdir(),
        key=lambda p: int(p.name[:2])
    )
    
    cartella_corretta = sottocartelle[-1]

    file_trovati = [file for ext in ESTENSIONI for file in cartella_corretta.glob(ext)]

    return Path(cartella_corretta), file_trovati


def _cancella_file(percorso: Path, nome_ricerca: str = None):
    '''
    Ricerca e cancella un file che corrisponde al pattern nome_ricerca
    nella directory percorso (es. CAMPAGNA_{utente}).
    Stampa un errore se non trovato.
    next --> serve per iterare e prendere il primo elemento dell'iteratore
    '''
    import re

    match = next(
        (f for f in percorso.iterdir() if f.is_file() and re.search(nome_ricerca, f.name)),
        None
    )

    if not match:
        print(f"[ERRORE] Nessun file trovato con pattern '{nome_ricerca}' in '{percorso}'")
        return

    match.unlink()
