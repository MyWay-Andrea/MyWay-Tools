from pathlib import Path
from copy import copy 
import shutil
from colorama import Fore, init
init(autoreset = True)
from pathlib import Path
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

#trova file campagne nella cartella 00_SCAMBIO DOCUMENTI / CAMPAGNA  / ...
def converti_xls_in_xlsx(cartella):
    file_xls = [
        file
        for file in cartella.glob("*.xls")
        if not file.name.startswith("~$")
    ]

    if not file_xls:
        return

    import win32com.client

    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    try:
        for file in file_xls:
            destinazione = file.with_suffix(".xlsx")
            workbook = excel.Workbooks.Open(str(file.resolve()))
            try:
                workbook.SaveAs(str(destinazione.resolve()), FileFormat=51)
            finally:
                workbook.Close(False)

            if destinazione.exists():
                file.unlink()
                print(Fore.GREEN + f"Convertito in xlsx: {destinazione.name}")
    finally:
        excel.Quit()


def trova_raw_file(path_cartella):
    ESTENSIONI = ["*.xlsx"]
    sottocartelle = sorted(
        path_cartella.iterdir(),
        key=lambda p: int(p.name[:2])
    )
    
    cartella_corretta = sottocartelle[-1]

    print(cartella_corretta)


    converti_xls_in_xlsx(cartella_corretta)

    file_trovati = [
        file
        for ext in ESTENSIONI
        for file in cartella_corretta.glob(ext)
        if not file.name.startswith("~$")
    ]

    return Path(cartella_corretta), file_trovati


def elimina_carica_campagna_agente_teams(agente, file_pronto, venditori_path):

    if agente not in venditori_path:
        print(f"Agente non trovato: {agente}")
        return

    # 1. trova percorso agente
    destinazioni = venditori_path[agente]


    # Se è una singola path → trasformala in lista
    if not isinstance(destinazioni, list):
        destinazioni = [destinazioni]


    for path in destinazioni:
        for file in path.glob("*CAMPAGNA*"):
            if file.is_file():
                file.unlink()

        # . salvataggio file di riferimento
        dest = path / file_pronto.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_pronto, dest)
        print(Fore.GREEN + f"{agente} salvato su Temas")


#FUNZIONI PER CREAZIONE FOGLI 
#----------------------------------------------------------------------------
def copia_stile_cella(cella_origine, cella_destinazione):
    if cella_origine.has_style:
        cella_destinazione.font = copy(cella_origine.font)
        cella_destinazione.border = copy(cella_origine.border)
        cella_destinazione.fill = copy(cella_origine.fill)
        cella_destinazione.number_format = copy(cella_origine.number_format)
        cella_destinazione.protection = copy(cella_origine.protection)
        cella_destinazione.alignment = copy(cella_origine.alignment)

