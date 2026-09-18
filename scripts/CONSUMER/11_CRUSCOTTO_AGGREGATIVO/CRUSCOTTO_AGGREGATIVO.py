from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path

from colorama import Fore, init

from calcola_kpi import calcola_kpi
from carica_dati import (
    carica_business,
    carica_pedonalita,
    carica_tracciamenti,
)
from config import NOME_OUTPUT, trova_sorgenti
from genera_cruscotto import genera_cruscotto
from graph_sharepoint import GraphSharePointClient


init(autoreset=True)


def main() -> None:
    print("=== CRUSCOTTO AGGREGATIVO ===\n")
    print("Ricerca dinamica delle sorgenti...")
    client_sharepoint = GraphSharePointClient()
    sorgenti = trova_sorgenti(client_sharepoint)

    print("Lettura BUSINESS GIORNALIERO...")
    business, target = carica_business(sorgenti["business"], client_sharepoint)
    print("Lettura tracciamenti negozi (ENERGIA, GADGET, DIGI)...")
    energia, gadget, digi = carica_tracciamenti(
        sorgenti["tracciamenti"],
        client_sharepoint,
    )
    print("Lettura PEDONALITA...")
    pedonalita = carica_pedonalita(sorgenti["pedonalita"], client_sharepoint)

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
    with TemporaryDirectory(prefix="cruscotto_aggregativo_") as cartella_temp:
        percorso = genera_cruscotto(
            dati,
            sorgenti,
            Path(cartella_temp) / NOME_OUTPUT,
        )
        contenuto = percorso.read_bytes()
        caricati = []
        for nome, destinazione in sorgenti["destinazioni"].items():
            risultato = client_sharepoint.carica_bytes(
                destinazione["drive_id"],
                destinazione["cartella"],
                NOME_OUTPUT,
                contenuto,
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            )
            caricati.append((nome, risultato["webUrl"]))

    print(Fore.GREEN + "\nOK - Cruscotti caricati su SharePoint:")
    for nome, indirizzo in caricati:
        print(Fore.GREEN + f"- {nome}: {indirizzo}")


if __name__ == "__main__":
    main()
