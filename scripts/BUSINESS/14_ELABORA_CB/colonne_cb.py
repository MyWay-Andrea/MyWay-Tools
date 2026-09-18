from pathlib import Path
import json


PATH_MAPPATURA = Path(__file__).with_name("mappatura_colonne_cb.json")
CAMPI_OPZIONALI = {"sede_legale", "email"}


def normalizza_colonna(nome) -> str:
    return str(nome).strip().lower()


def leggi_alias_colonne() -> dict[str, list[str]]:
    with PATH_MAPPATURA.open("r", encoding="utf-8") as file:
        return json.load(file)


def trova_colonne_azienda(colonne_cb) -> dict[str, str]:
    colonne_lower = {
        normalizza_colonna(colonna): colonna
        for colonna in colonne_cb
    }
    colonne_trovate = {}

    for campo, alias in leggi_alias_colonne().items():
        corrispondenze = list(dict.fromkeys(
            colonne_lower[normalizza_colonna(nome)]
            for nome in alias
            if normalizza_colonna(nome) in colonne_lower
        ))

        if not corrispondenze:
            if campo in CAMPI_OPZIONALI:
                continue

            raise ValueError(
                f"Colonna CB non trovata per '{campo}'. Alias controllati: {alias}"
            )

        if len(corrispondenze) > 1:
            raise ValueError(
                f"Più colonne CB corrispondono a '{campo}': {corrispondenze}"
            )

        colonne_trovate[campo] = corrispondenze[0]

    return colonne_trovate
