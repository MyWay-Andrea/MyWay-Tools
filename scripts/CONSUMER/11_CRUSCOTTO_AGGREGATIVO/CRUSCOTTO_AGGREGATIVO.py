from __future__ import annotations

from colorama import Fore, init

from calcola_kpi import calcola_kpi
from carica_dati import (
    carica_business,
    carica_pedonalita,
    carica_tracciamenti,
)
from config import PATH_OUTPUT, PATH_OUTPUT_TEAM_CONSUMER, trova_sorgenti
from genera_cruscotto import genera_cruscotto


init(autoreset=True)


def main() -> None:
    print("=== CRUSCOTTO AGGREGATIVO ===\n")
    print("Ricerca dinamica delle sorgenti...")
    sorgenti = trova_sorgenti()

    print("Lettura BUSINESS GIORNALIERO...")
    business, target = carica_business(sorgenti["business"])
    print("Lettura tracciamenti negozi (ENERGIA, GADGET, DIGI)...")
    energia, gadget, digi = carica_tracciamenti(sorgenti["tracciamenti"])
    print("Lettura PEDONALITA...")
    pedonalita = carica_pedonalita(sorgenti["pedonalita"])

    print("Calcolo indicatori...")
    dati = calcola_kpi(
        business=business,
        target=target,
        energia=energia,
        gadget=gadget,
        digi=digi,
        pedonalita=pedonalita,
    )

    print("Generazione CRUSCOTTO.xlsx...")
    percorso = genera_cruscotto(dati, sorgenti, PATH_OUTPUT)
    genera_cruscotto(dati, sorgenti, PATH_OUTPUT_TEAM_CONSUMER)
    print(
        Fore.GREEN
        + "\nOK - Cruscotti creati:"
        + f"\n- {percorso}"
        + f"\n- {PATH_OUTPUT_TEAM_CONSUMER}"
    )


if __name__ == "__main__":
    main()
