from pathlib import Path
import json


PATH_MAPPATURA = Path(__file__).with_name("mappatura_consistenze.json")


def normalizza_nome_colonna(nome) -> str:
    return str(nome).strip().lower()


def leggi_mappatura_consistenze() -> list[dict]:
    with PATH_MAPPATURA.open("r", encoding="utf-8") as file:
        dati = json.load(file)

    consistenze = dati.get("consistenze")

    if not isinstance(consistenze, list):
        raise ValueError(
            "La chiave 'consistenze' deve contenere una lista"
        )

    return consistenze


def crea_mappa_alias_consistenze() -> dict[str, str]:
    mappa_alias = {}

    for consistenza in leggi_mappatura_consistenze():
        campo_crm = consistenza["campo_crm"]

        for alias in consistenza["alias_cb"]:
            alias_lower = normalizza_nome_colonna(alias)
            campo_esistente = mappa_alias.get(alias_lower)

            if campo_esistente and campo_esistente != campo_crm:
                raise ValueError(
                    f"L'alias '{alias}' è associato a più campi CRM"
                )

            mappa_alias[alias_lower] = campo_crm

    return mappa_alias


def associa_colonne_cb(colonne_cb) -> tuple[dict, list[str]]:
    mappa_alias = crea_mappa_alias_consistenze()
    associazioni = {}

    for colonna in colonne_cb:
        campo_crm = mappa_alias.get(normalizza_nome_colonna(colonna))

        if campo_crm:
            associazioni[colonna] = campo_crm

    campi_crm_trovati = set(associazioni.values())
    campi_crm_configurati = {
        consistenza["campo_crm"]
        for consistenza in leggi_mappatura_consistenze()
    }
    campi_mancanti = sorted(campi_crm_configurati - campi_crm_trovati)

    return associazioni, campi_mancanti
