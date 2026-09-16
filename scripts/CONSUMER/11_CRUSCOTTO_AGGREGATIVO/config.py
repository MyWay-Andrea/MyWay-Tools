from __future__ import annotations

import sys
from pathlib import Path


CARTELLA_CONSUMER = Path(__file__).resolve().parents[1]
if str(CARTELLA_CONSUMER) not in sys.path:
    sys.path.insert(0, str(CARTELLA_CONSUMER))

from common.negozi import (  # noqa: E402
    PATH_SHAREPOINT,
    PATH_TEAM_CONSUMER,
    carica_negozi,
    trova_cartelle_negozi,
)
from common.ricerca_file import cerca_file_unico  


NOME_OUTPUT = "CRUSCOTTO.xlsx"
PATH_OUTPUT = (
    PATH_SHAREPOINT
    / "CONSUMER - MANDELLI - CONSUMER - MANDELLI"
    / NOME_OUTPUT
)
PATH_OUTPUT_TEAM_CONSUMER = PATH_TEAM_CONSUMER / NOME_OUTPUT
PATH_PARQUET = (
    PATH_SHAREPOINT / "00_SCAMBIO DOCUMENTI - 00_SCAMBIO DOCUMENTI" / ".parquet"
)

# Il file config/negozi.json e' la fonte per elenco e ordine dei negozi.
# EXTRA aggrega gli inserimenti non associati a un negozio configurato.
ORDINE_NEGOZI = [*carica_negozi(), "EXTRA"]

MAPPA_PEDONALITA = {
    "Carpi": "CARPI",
    "Fidenza": "FIDENZA",
    "Parma Eurosia": "EUROSIA",
    "Parma Torri": "TORRI",
    "Piacenza Galassia": "GALASSIA",
    "Sassuolo": "SASSUOLO",
}

CROSS_SELLING = "SOLO GADGET"


def trova_sorgenti() -> dict[str, object]:
    cartelle_negozi = trova_cartelle_negozi()

    business = cerca_file_unico(
        PATH_TEAM_CONSUMER,
        ("business", "giornaliero"),
    )
    pedonalita = cerca_file_unico(
        PATH_PARQUET,
        ("pedonalit",),
        estensioni=(".parquet",),
    )

    tracciamenti: dict[str, Path] = {}

    for negozio, cartella in cartelle_negozi.items():
        try:
            tracciamenti[negozio] = cerca_file_unico(
                cartella,
                ("tracciamento", negozio),
                ricorsiva=False,
            )
        except FileNotFoundError as errore:
            print(f"Attenzione: {errore}")

    return {
        "business": business,
        "pedonalita": pedonalita,
        "tracciamenti": tracciamenti,
    }
