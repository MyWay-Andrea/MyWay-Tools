from collections import Counter, defaultdict
import os
import re

import pandas as pd

from colonne_cb import trova_colonne_azienda
from config import COMMERCIALI


STATI_BLOCCANTI = {
    "partita_iva_non_valida",
    "conflitto_commerciale",
    "conflitto_identificativi",
    "duplicata_nel_crm",
}


def normalizza_partita_iva(valore) -> str | None:
    if valore is None or pd.isna(valore):
        return None

    partita_iva = str(valore).strip().upper()

    if partita_iva.endswith(".0"):
        partita_iva = partita_iva[:-2]

    if partita_iva.startswith("IT"):
        partita_iva = partita_iva[2:]

    partita_iva = re.sub(r"\D", "", partita_iva)

    if len(partita_iva) != 11:
        return None

    return partita_iva


def normalizza_custcode(valore) -> str | None:
    if valore is None or pd.isna(valore):
        return None

    custcode = str(valore).strip()

    if custcode.endswith(".0"):
        custcode = custcode[:-2]

    return custcode.lower() or None


def valore_colonna_opzionale(riga, colonna: str | None) -> str:
    if not colonna:
        return "N/A"

    valore = riga.get(colonna)

    if valore is None or pd.isna(valore) or not str(valore).strip():
        return "N/A"

    return valore


def indicizza_aziende_crm(aziende_crm: list[dict]) -> tuple[dict, dict]:
    aziende_per_piva = defaultdict(list)
    aziende_per_custcode = defaultdict(list)

    for azienda in aziende_crm:
        partita_iva = normalizza_partita_iva(azienda.get("vatId"))
        custcode = normalizza_custcode(azienda.get("FF_VIC_CUSTCODE"))

        if partita_iva:
            aziende_per_piva[partita_iva].append(azienda)

        if custcode:
            aziende_per_custcode[custcode].append(azienda)

    return dict(aziende_per_piva), dict(aziende_per_custcode)


def cerca_azienda_crm(
    partita_iva: str | None,
    custcode: str | None,
    aziende_per_piva: dict,
    aziende_per_custcode: dict,
) -> tuple[list[dict], str, bool]:
    trovate_piva = aziende_per_piva.get(partita_iva, []) if partita_iva else []
    trovate_custcode = (
        aziende_per_custcode.get(custcode, [])
        if custcode else []
    )

    ids_piva = {azienda.get("id") for azienda in trovate_piva}
    ids_custcode = {azienda.get("id") for azienda in trovate_custcode}

    if ids_piva and ids_custcode and ids_piva != ids_custcode:
        return [], "Partita IVA / custcode", True

    if trovate_piva and trovate_custcode:
        return trovate_piva, "Partita IVA + custcode", False

    if trovate_piva:
        return trovate_piva, "Partita IVA", False

    if trovate_custcode:
        return trovate_custcode, "custcode", False

    return [], "Nessuna corrispondenza", False


def nomi_commerciali_da_id(ids, commerciale_per_id: dict) -> str:
    nomi = [
        commerciale_per_id.get(account_id, f"ID {account_id}")
        for account_id in ids
    ]
    return ", ".join(nomi) if nomi else "Nessuno"


def analizza_aziende(
    df: pd.DataFrame,
    aziende_crm: list[dict],
    id_per_commerciale: dict,
    commerciale_per_id: dict,
) -> dict:
    from consistenze import associa_colonne_cb

    colonne = trova_colonne_azienda(df.columns)
    mapping_consistenze, _ = associa_colonne_cb(df.columns)
    commerciali_configurati = {
        commerciale["nome_crm"].strip().lower()
        for commerciale in COMMERCIALI
    }
    filtro_commerciali = (
        df["COMMERCIALE"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(commerciali_configurati)
    )
    righe_escluse = int((~filtro_commerciali).sum())

    aziende_per_piva, aziende_per_custcode = indicizza_aziende_crm(
        aziende_crm
    )
    righe_per_piva = defaultdict(list)
    risultati = []

    for _, riga in df.iterrows():
        partita_iva_originale = riga.get(colonne["partita_iva"])
        partita_iva = normalizza_partita_iva(partita_iva_originale)
        custcode_originale = riga.get(colonne["custcode"])
        custcode = normalizza_custcode(custcode_originale)
        dati_riga = {
            "partita_iva": partita_iva,
            "partita_iva_originale": partita_iva_originale,
            "ragione_sociale": riga.get(colonne["ragione_sociale"]),
            "custcode": custcode,
            "custcode_originale": custcode_originale,
            "commerciale": riga.get("COMMERCIALE"),
            "sede_legale": valore_colonna_opzionale(
                riga,
                colonne.get("sede_legale"),
            ),
            "email": valore_colonna_opzionale(
                riga,
                colonne.get("email"),
            ),
        }

        # Estrai le consistenze dalle colonne mappate
        consistenze = {}
        for col_cb, campo_crm in mapping_consistenze.items():
            if col_cb in riga and pd.notna(riga[col_cb]):
                valore = riga[col_cb]
                # Se è una stringa, prova a convertirla in numero
                if isinstance(valore, str) and valore.strip():
                    # Sostituisci la virgola con il punto
                    try:
                        valore = float(valore.replace(",", "."))
                    except ValueError:
                        # Se non è un numero, lascia come stringa
                        pass
                consistenze[campo_crm] = valore
        dati_riga["consistenze"] = consistenze

        commerciale_normalizzato = str(
            dati_riga.get("commerciale") or ""
        ).strip().lower()
        if commerciale_normalizzato not in commerciali_configurati:
            dati_riga.update({
                "stato": "commerciale_non_mappato",
                "azienda_crm": "",
                "commerciale_crm": "",
            })
            risultati.append(dati_riga)
            continue

        if partita_iva is None and custcode is None:
            dati_riga.update({
                "stato": "partita_iva_non_valida",
                "azienda_crm": "",
                "commerciale_crm": "",
            })
            risultati.append(dati_riga)
            continue

        chiave_gruppo = partita_iva or f"custcode:{custcode}"
        righe_per_piva[chiave_gruppo].append(dati_riga)

    for _, righe_cb in righe_per_piva.items():
        commerciali = {
            str(riga["commerciale"]).strip()
            for riga in righe_cb
            if (
                pd.notna(riga["commerciale"])
                and str(riga["commerciale"]).strip()
            )
        }
        risultato = dict(righe_cb[0])
        risultato["righe_cb"] = len(righe_cb)

        if len(commerciali) != 1:
            risultato.update({
                "stato": "conflitto_commerciale",
                "commerciale": ", ".join(sorted(commerciali)),
                "azienda_crm": "",
                "commerciale_crm": "",
            })
            risultati.append(risultato)
            continue

        commerciale = next(iter(commerciali))
        risultato["commerciale"] = commerciale
        account_id_atteso = id_per_commerciale.get(commerciale)
        risultato["commerciale_id"] = account_id_atteso

        aziende_trovate, metodo_confronto, conflitto_identificativi = (
            cerca_azienda_crm(
                risultato.get("partita_iva"),
                risultato.get("custcode"),
                aziende_per_piva,
                aziende_per_custcode,
            )
        )
        risultato["metodo_confronto"] = metodo_confronto

        if conflitto_identificativi:
            risultato.update({
                "stato": "conflitto_identificativi",
                "azienda_crm": "",
                "commerciale_crm": "",
            })
            risultati.append(risultato)
            continue

        if not aziende_trovate:
            risultato.update({
                "stato": "da_creare",
                "azienda_crm": "",
                "commerciale_crm": "Nessuno",
            })
            risultati.append(risultato)
            continue

        if len(aziende_trovate) > 1:
            risultato.update({
                "stato": "duplicata_nel_crm",
                "azienda_crm": " | ".join(
                    str(azienda.get("companyName") or "")
                    for azienda in aziende_trovate
                ),
                "commerciale_crm": "",
            })
            risultati.append(risultato)
            continue

        azienda_crm = aziende_trovate[0]
        sales_persons = azienda_crm.get("salesPersons") or []

        if not isinstance(sales_persons, list):
            sales_persons = [sales_persons]

        sales_persons = set(sales_persons)

        if account_id_atteso is None:
            risultato.update({
                "stato": "presente_commerciale_non_verificabile",
                "azienda_crm": azienda_crm.get("companyName") or "",
                "azienda_crm_id": azienda_crm.get("id"),
                "partita_iva_crm": azienda_crm.get("vatId"),
                "custcode_crm": azienda_crm.get("FF_VIC_CUSTCODE"),
                "commerciale_crm": nomi_commerciali_da_id(
                    sales_persons,
                    commerciale_per_id,
                ),
            })
            risultati.append(risultato)
            continue

        stato = (
            "presente_corretta"
            if sales_persons == {account_id_atteso}
            else "da_riassegnare"
        )
        risultato.update({
            "stato": stato,
            "azienda_crm": azienda_crm.get("companyName") or "",
            "azienda_crm_id": azienda_crm.get("id"),
            "partita_iva_crm": azienda_crm.get("vatId"),
            "custcode_crm": azienda_crm.get("FF_VIC_CUSTCODE"),
            "commerciale_crm": nomi_commerciali_da_id(
                sales_persons,
                commerciale_per_id,
            ),
            "nuovo_sales_person_id": account_id_atteso,
        })
        risultati.append(risultato)

    risultati.sort(
        key=lambda riga: (
            0 if riga.get("stato") == "da_creare" else 1,
            str(riga.get("commerciale") or "").lower(),
            str(riga.get("ragione_sociale") or "").lower(),
        )
    )

    limite_test = os.getenv("CRM_TEST_LIMIT")
    if limite_test:
        risultati = risultati[:int(limite_test)]

    riepilogo = Counter(riga["stato"] for riga in risultati)
    per_commerciale = defaultdict(Counter)

    for riga in risultati:
        commerciale = riga.get("commerciale") or "SENZA COMMERCIALE"
        per_commerciale[commerciale][riga["stato"]] += 1

    return {
        "risultati": risultati,
        "riepilogo": dict(riepilogo),
        "per_commerciale": {
            commerciale: dict(conteggi)
            for commerciale, conteggi in per_commerciale.items()
        },
        "conflitti_bloccanti": sum(
            riepilogo.get(stato, 0)
            for stato in STATI_BLOCCANTI
        ),
        "righe_escluse": righe_escluse,
    }
