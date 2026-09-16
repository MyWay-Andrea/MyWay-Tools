import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from config import (
    API_KEY,
    BASE_URL,
    COLONNE_APPUNTAMENTI,
    STATO_ATTIVITA_MAP,
    TIPO_ATTIVITA_APPUNTAMENTO,
    TIPO_APP_MAP,
)


session = requests.Session()
UTC = ZoneInfo("UTC")
ROME = ZoneInfo("Europe/Rome")
company_cache = {}
user_cache = {}
lead_cache = {}


def get_json(endpoint: str, params=None):
    params = dict(params or {})
    params["apikey"] = API_KEY
    response = session.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def esplora_campi():
    """Mostra un'attività API per verificare futuri cambiamenti dello schema CRM."""
    attività = get_json("Activity/Search", {"top": 1, "skip": 0})
    print(json.dumps(attività[0] if attività else {}, indent=2, ensure_ascii=False))


def get_all_activities():
    # Il CRM restituisce 503 con pagine troppo grandi: 10 è il batch già
    # utilizzato con successo dall'estrazione opportunità.
    attività, top, offset, pagine = [], 10, 0, 0
    while True:
        batch = None
        for tentativo in range(1, 6):
            try:
                batch = get_json("Activity/Search", {"top": top, "skip": offset})
                break
            except requests.RequestException as errore:
                print(f"Errore download attività ({tentativo}/5): {errore}", flush=True)
                time.sleep(5 * tentativo)

        if batch is None:
            raise RuntimeError(f"Troppi errori durante il download attività, skip={offset}")
        if not batch:
            break
        attività.extend(batch)
        pagine += 1
        if len(batch) < top:
            break
        offset += top

    appuntamenti = [
        attività_api
        for attività_api in attività
        if attività_api.get("type") == TIPO_ATTIVITA_APPUNTAMENTO
    ]
    print(f"{pagine} pagine | {len(attività)} attività | {len(appuntamenti)} appuntamenti")
    return appuntamenti


def _formatta_data_api(valore):
    if not valore:
        return None
    try:
        valore = str(valore).replace("Z", "").replace("T", " ")[:19]
        data_utc = datetime.strptime(valore, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        return data_utc.astimezone(ROME).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _estrai_nome_lead(lead):
    for chiave in ("companyName", "name", "fullName", "firstName"):
        valore = lead.get(chiave)
        if valore:
            return valore
    return None


def prefetch_anagrafiche(appuntamenti):
    company_ids = {item.get("companyId") for item in appuntamenti if item.get("companyId")}
    user_ids = {
        user_id
        for item in appuntamenti
        for user_id in (item.get("ownerId"), item.get("idCompanion"))
        if user_id
    }
    lead_ids = {item.get("leadId") for item in appuntamenti if item.get("leadId")}

    def fetch_company(company_id):
        try:
            azienda = get_json(f"Company/{company_id}")
            return company_id, azienda.get("companyName")
        except requests.RequestException:
            return company_id, None

    def fetch_user(user_id):
        try:
            account = get_json("Account/Get", {"id": user_id})
            aliases = account.get("aliases") or []
            return user_id, aliases[0].upper() if aliases else None
        except requests.RequestException:
            return user_id, None

    def fetch_lead(lead_id):
        try:
            lead = get_json(f"Lead/{lead_id}")
            return lead_id, _estrai_nome_lead(lead)
        except requests.RequestException:
            return lead_id, None

    for ids, funzione, cache in (
        (company_ids, fetch_company, company_cache),
        (user_ids, fetch_user, user_cache),
        (lead_ids, fetch_lead, lead_cache),
    ):
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(funzione, item_id) for item_id in ids]
            for future in as_completed(futures):
                item_id, valore = future.result()
                cache[item_id] = valore


def main() -> pd.DataFrame:
    """Estrae dall'API CRM i soli appuntamenti e li mappa sul formato storico."""
    appuntamenti = get_all_activities()
    prefetch_anagrafiche(appuntamenti)

    righe = []
    for attività in appuntamenti:
        cliente = company_cache.get(attività.get("companyId"))
        if not cliente:
            cliente = lead_cache.get(attività.get("leadId"))
        nota = attività.get("description") or attività.get("description2") or None
        righe.append({
            "Data":                 _formatta_data_api(attività.get("activityDate")),
            "Orario":               None,
            "Cliente":              cliente,
            "In carico a":          user_cache.get(attività.get("ownerId")),
            "Accompagnato da":      user_cache.get(attività.get("idCompanion")),
            "Indirizzo":            attività.get("FF_VIC_INDIRIZZO"),
            "Fatta/da fare":        STATO_ATTIVITA_MAP.get(attività.get("state")),
            "Tipo di appuntamento": TIPO_APP_MAP.get(attività.get("FF_VIC_TIPOAPP")),
            "Nota interna":         nota,
        })

    return pd.DataFrame(righe, columns=COLONNE_APPUNTAMENTI)


if __name__ == "__main__":
    print(main())
