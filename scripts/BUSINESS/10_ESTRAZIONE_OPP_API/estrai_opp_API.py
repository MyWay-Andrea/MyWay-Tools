import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from AGGREGA_STORICO import aggiorna_storico
from config import API_KEY, BASE_URL, COLONNE_OPPORTUNITA, STATO_MAP, TIP_SERVIZIO_MAP
from formatta_opportunita import main as formatta_opportunita


session = requests.Session()
UTC = ZoneInfo("UTC")
ROME = ZoneInfo("Europe/Rome")


def get_json(endpoint, params=None):
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


def format_date(valore):
    """Converte una data UTC ISO in data locale Europe/Rome."""
    if not valore:
        return None
    try:
        valore = str(valore).replace("Z", "").replace("T", " ")[:19]
        data_utc = datetime.strptime(valore, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        return data_utc.astimezone(ROME).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return valore


def explore_opportunity_fields():
    """Stampa i campi disponibili nella prima opportunità restituita dall'API."""
    sample = get_json("Opportunity/Search", {"top": 1, "skip": 0})
    if sample:
        print(json.dumps(sample[0], indent=2, ensure_ascii=False))
    else:
        print("Nessuna opportunità trovata.")


def get_all_opportunities():
    """Scarica tutte le opportunità con paginazione e retry automatico."""
    opportunita, top, offset, pagine = [], 10, 0, 0
    while True:
        batch = None
        for tentativo in range(1, 6):
            try:
                batch = get_json("Opportunity/Search", {"top": top, "skip": offset})
                break
            except requests.RequestException as errore:
                print(f"  Errore (tentativo {tentativo}/5): {errore}", flush=True)
                time.sleep(5 * tentativo)

        if batch is None:
            raise RuntimeError(f"Troppi errori durante il download, skip={offset}")
        if not batch:
            break

        opportunita.extend(batch)
        pagine += 1
        if len(batch) < top:
            break
        offset += top

    print(f"  {pagine} pagine | {len(opportunita)} opportunità totali")
    return opportunita


company_cache = {}
user_cache = {}
catalog_cache = {}


def get_company_info(company_id):
    return company_cache.get(company_id, (None, None))


def get_user_name(user_id):
    return user_cache.get(user_id)


def get_product_tipology(product_id):
    return catalog_cache.get(product_id)


def prefetch_companies_and_users(opportunita):
    company_ids = {opp.get("crossId") for opp in opportunita if opp.get("crossId")}
    user_ids = {user for opp in opportunita for user in (opp.get("salesPersons") or [])}
    catalog_ids = {
        prodotto.get("productId")
        for opp in opportunita
        for prodotto in (opp.get("products") or [])
        if prodotto.get("productId")
    }

    print(
        f"  Aziende uniche: {len(company_ids)} | Utenti unici: {len(user_ids)} | "
        f"Prodotti unici: {len(catalog_ids)}",
        flush=True,
    )

    def fetch_company(company_id):
        try:
            data = get_json(f"Company/{company_id}")
            return company_id, (data.get("companyName"), data.get("vatId"))
        except requests.RequestException:
            return company_id, (None, None)

    def fetch_user(user_id):
        try:
            account = get_json("Account/Get", {"id": user_id})
            aliases = account.get("aliases") or []
            return user_id, aliases[0].upper() if aliases else None
        except requests.RequestException:
            return user_id, None

    def fetch_catalog(product_id):
        try:
            prodotto = get_json("Catalog/Get", {"id": product_id})
            return product_id, prodotto.get("FF_Pers_TipoServizio")
        except requests.RequestException:
            return product_id, None

    for ids, funzione, cache, etichetta in (
        (company_ids, fetch_company, company_cache, "Aziende"),
        (user_ids, fetch_user, user_cache, "Utenti"),
        (catalog_ids, fetch_catalog, catalog_cache, "Prodotti"),
    ):
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(funzione, item_id) for item_id in ids]
            for indice, future in enumerate(as_completed(futures), 1):
                item_id, risultato = future.result()
                cache[item_id] = risultato
                print(f"  {etichetta}: {indice}/{len(ids)}", end="\r", flush=True)
        print()

    print("  Prefetch completato.", flush=True)


def _calcola_importo(prodotto):
    quantita = pd.to_numeric(prodotto.get("productQta"), errors="coerce")
    prezzo = pd.to_numeric(prodotto.get("productPrice"), errors="coerce")
    return quantita * prezzo if pd.notna(quantita) and pd.notna(prezzo) else None


def main():
    """Estrae e mappa le opportunità API sullo schema standard condiviso."""
    print("=== Estrazione opportunità CRM in Cloud ===\n")
    inizio = time.perf_counter()

    print("1. Download opportunità...")
    opportunita = get_all_opportunities()

    print("2. Prefetch aziende, commerciali e prodotti...")
    prefetch_companies_and_users(opportunita)

    print("\n3. Elaborazione righe...")
    righe = []
    for opportunita_api in opportunita:
        azienda, partita_iva = get_company_info(opportunita_api.get("crossId"))
        commerciali = opportunita_api.get("salesPersons") or []
        commerciale = get_user_name(commerciali[0]) if commerciali else None
        if commerciale == "BO":
            commerciale = "CRM My Way"

        stato = STATO_MAP.get(opportunita_api.get("phase"), opportunita_api.get("phase"))
        for prodotto in opportunita_api.get("products") or []:
            codice_tipologia = get_product_tipology(prodotto.get("productId"))
            tipologia = TIP_SERVIZIO_MAP.get(str(codice_tipologia), codice_tipologia)
            righe.append({
                "Codice Opportunità":               f"TO400000{opportunita_api.get('code')}",
                "Potenziale cliente (Opportunità)": azienda,
                "Partita IVA (Opportunità)":        partita_iva,
                "Proprietario (Opportunità)":       commerciale,
                "Stato (Opportunità)":              stato,
                "Data creazione":                   format_date(opportunita_api.get("createdDate")),
                "Data chiusura prev. (Opportunità)":format_date(opportunita_api.get("closeDate")),
                "Data modifica":                    format_date(opportunita_api.get("lastModifiedDate")),
                "Tipologia Servizio":               tipologia,
                "Prodotto esistente":               prodotto.get("productName"),
                "Quantità":                         prodotto.get("productQta"),
                "Prezzo":                           prodotto.get("productPrice"),
                "Importo totale":                   _calcola_importo(prodotto),
                "Probabilità (Opportunità)":        opportunita_api.get("probability"),
            })

    df = pd.DataFrame(righe, columns=COLONNE_OPPORTUNITA)
    print(f"   Righe generate: {len(df)}")
    print(f"Tempo di esecuzione: {time.perf_counter() - inizio:.2f} secondi")
    return df


def esegui_flusso_completo():
    """Esegue estrazione API, output opportunità e aggiornamento dello storico."""
    df_estratto = main()
    df_formattato = formatta_opportunita(df_estratto)
    aggiorna_storico(df_formattato)
    return df_formattato


if __name__ == "__main__":
    esegui_flusso_completo()
