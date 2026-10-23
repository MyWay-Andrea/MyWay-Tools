"""Stampa in JSON l'anagrafica CRM di una partita IVA specifica.

Esecuzione dalla cartella dello script:
    python estrai_anagrafica_crm_json.py
"""

import json

from console import info, titolo
from crm_anagrafica import estrai_aziende, get_json


PARTITA_IVA = "10551050965"


def main() -> None:
    titolo("Anagrafica azienda CRM")
    risposta = get_json(
        "Company/Search",
        {"$filter": f"vatId eq '{PARTITA_IVA}'", "$top": 2},
    )
    aziende = estrai_aziende(risposta)

    if not aziende:
        info(f"Nessuna azienda trovata con vatId {PARTITA_IVA}.")
        return

    print(json.dumps(aziende, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
