from pathlib import Path
import shutil
import os

def copia_in_onedrive(file_agente, percorsi, agente=None):
    if isinstance(percorsi, dict):
        cartella_dest = percorsi[agente]
    else:
        cartella_dest = percorsi

    file_agente = Path(file_agente)
    file_dest = cartella_dest / file_agente.name
    file_tmp = cartella_dest / (file_agente.stem + "_tmp.xlsx")

    # 1. Copia con nome temporaneo (Teams non conosce ancora questo file)
    shutil.copy2(file_agente, file_tmp)

    # 2. Rinomina atomico: sovrascrive il vecchio in un'unica operazione
    #    os.replace è atomico su Windows — Teams vede solo il file finito
    os.replace(file_tmp, file_dest)

    return file_dest