from __future__ import annotations

import re
from collections import defaultdict
from datetime import date


CATEGORIE = (
    "opportunita_scadute",
    "appuntamenti_arretrati",
    "appuntamenti_oggi",
)


def normalizza_nome(valore: str | None) -> str:
    if not valore:
        return ""
    return " ".join(re.findall(r"[a-z0-9]+", valore.casefold()))


def crea_indice_venditori(venditori: list[dict]) -> dict[str, str]:
    indice: dict[str, str] = {}
    for venditore in venditori:
        canonico = venditore["nome_crm"]
        for nome in [canonico, *(venditore.get("alias_cb") or [])]:
            normalizzato = normalizza_nome(nome)
            if normalizzato:
                indice[normalizzato] = canonico
    return indice


def risolvi_proprietario(nome: str | None, indice: dict[str, str]) -> str | None:
    return indice.get(normalizza_nome(nome))


def applica_regole(
    opportunita: list[dict],
    appuntamenti: list[dict],
    oggi: date,
    venditori: list[dict],
) -> dict[str, dict[str, list[dict]]]:
    indice = crea_indice_venditori(venditori)
    risultati: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: {categoria: [] for categoria in CATEGORIE}
    )

    for item in opportunita:
        if item.get("stato") != "Aperta":
            continue
        proprietario = risolvi_proprietario(item.get("proprietario"), indice)
        destinatario = proprietario or "__NON_ASSEGNATO__"
        data_chiusura = item.get("data_chiusura")
        if data_chiusura is not None and hasattr(data_chiusura, "date") and data_chiusura.date() <= oggi:
            risultati[destinatario]["opportunita_scadute"].append(item)

    for item in appuntamenti:
        stato = item.get("stato")
        data_appuntamento = item.get("data")

        if stato != "Attività da fare":
            continue
        proprietario = risolvi_proprietario(item.get("proprietario"), indice)
        destinatario = proprietario or "__NON_ASSEGNATO__"
        if data_appuntamento is not None and hasattr(data_appuntamento, "date") and data_appuntamento.date() < oggi:
            risultati[destinatario]["appuntamenti_arretrati"].append(item)
        elif data_appuntamento is not None and hasattr(data_appuntamento, "date") and data_appuntamento.date() == oggi:
            risultati[destinatario]["appuntamenti_oggi"].append(item)

    return dict(risultati)

