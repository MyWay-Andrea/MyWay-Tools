import requests
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from zoneinfo import ZoneInfo

from config import (
    API_KEY, BASE_URL,
    STAGE_MAP, LISTINO_MAP, TIPOLOGIA_SERVIZIO_MAP, TIPO_RELAZIONE_MAP,
    trova_periodo_gara
)

session = requests.Session()  # riusa la connessione HTTP

def get_json(endpoint, params=None):
    p = params or {}
    p["apikey"] = API_KEY
    r = session.get(f"{BASE_URL}/{endpoint}", params=p,
                    headers={"Content-Type": "application/json"},
                    timeout=30) 
    r.raise_for_status()
    return r.json()

UTC = ZoneInfo("UTC")
ROME = ZoneInfo("Europe/Rome")

def format_date(val):
    '''pulisce le date e le formatta nel modo corretto'''
    
    if not val:
        return None
    try:
        s = str(val).replace("Z", "").replace("T", " ")[:19]
        dt_utc = datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        dt_local = dt_utc.astimezone(ROME)
        return dt_local.strftime("%d/%m/%Y")
    except Exception:
        return val

def parse_api_date(val):
    if not val:
        return None

    try:
        s = str(val).replace("Z", "").replace("T", " ")[:19]
        dt_utc = datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        return dt_utc.astimezone(ROME).date()
    except Exception:
        try:
            dt = pd.to_datetime(val, errors="coerce")
            if pd.isna(dt):
                return None
            return dt.date()
        except Exception:
            return None

def riga_in_periodo_gara(row, inizio_gara, fine_gara):
    data_attivazione = parse_api_date(row.get("FF_VIC_ATTIVAZIONE"))

    if data_attivazione is None:
        return True

    return inizio_gara <= data_attivazione <= fine_gara


def riga_annullata_prima_periodo(ordine, row, inizio_gara):
    if ordine.get("stage") != 4:
        return False

    data_inserimento = parse_api_date(row.get("FF_VIC_OMNISALES"))
    if data_inserimento is None:
        return False

    return data_inserimento < inizio_gara

def filtra_ordini_periodo_gara(orders, inizio_gara, fine_gara):
    ordini_filtrati = []
    righe_totali = 0
    righe_filtrate = 0

    for ordine in orders:
        righe = ordine.get("rows", [])
        righe_totali += len(righe)

        righe_valide = [
            row for row in righe
            if (
                riga_in_periodo_gara(row, inizio_gara, fine_gara)
                and not riga_annullata_prima_periodo(ordine, row, inizio_gara)
            )
        ]

        if righe_valide:
            ordine_filtrato = dict(ordine)
            ordine_filtrato["rows"] = righe_valide
            ordini_filtrati.append(ordine_filtrato)
            righe_filtrate += len(righe_valide)

    return ordini_filtrati, righe_totali, righe_filtrate

def get_all_orders():
    ''' Estrae tutti gli ordini '''
    all_orders, top, offset = [], 10, 0
    conteggio = 1
    while True:
        #print(f"  Pagina: {conteggio} start: {offset}...", flush=True)
        
        tentativi = 0
        batch = None
        while tentativi < 5:
            try:
                batch = get_json("Order/Search", {"top": top, "skip": offset})
                break  # successo, esci dal retry
            except Exception as e:
                tentativi += 1
                print(f"  Errore (tentativo {tentativi}/5): {e}", flush=True)
                time.sleep(5 * tentativi)  # aspetta 5, 10, 15, 20, 25 sec
        
        if batch is None:
            print(f"  Troppi errori, interruzione a skip={offset}", flush=True)
            break
        if not batch:
            break
        all_orders.extend(batch)
        #print(f"  Totale finora: {len(all_orders)} ordini", flush=True)
        if len(batch) < top:
            break
        offset += top
        conteggio += 1
    print(f"  {conteggio} pagine con {len(all_orders)} ordini")
    return all_orders

company_cache = {}
user_cache = {}
catalog_cache = {}

def get_company_info(company_id):
    ''' 
    Controlla se l'id è già nella cache, se si restituisce il valore delal cache 
    sennò se lo cerca lui e lo restituisce
    '''
    if not company_id or company_id in company_cache:
        return company_cache.get(company_id)
    try:
        data = get_json(f"Company/{company_id}")
        company_cache[company_id] = (
            data.get("companyName"),        # nome
            data.get("vatId"),              # P.iva
            data.get("FF_VIC_ScalaSconti"), # Scala sconti
            data.get("FF_VIC_TIPOREL"))     # Tipo relazione
        
    except Exception:
        company_cache[company_id] = (None, None)
    return company_cache[company_id]


def get_user_name(user_id):
    ''' 
    Controlla se l'id è già nella cache, se si restituisce il valore delal cache 
    sennò se lo cerca lui e lo restituisce
    '''
    if not user_id or user_id in user_cache:
        return user_cache.get(user_id)
    try:
        account = get_json("Account/Get", {"id": user_id})
        aliases = account.get("aliases") or []      #aliases è l'endpoint per avere r.scimone
        user_cache[user_id] = aliases[0].upper() if aliases else None
    except Exception:
        user_cache[user_id] = None
    return user_cache[user_id]

def get_catalog_info(catalog_id):
    ''' 
    Controlla se l'id è già nella cache, se si restituisce il valore delal cache 
    sennò se lo cerca lui e lo restituisce
    '''
    if not catalog_id or catalog_id in catalog_cache:
        return catalog_cache.get(catalog_id)
    try:
        catalog = get_json("Catalog/Get", {"id": catalog_id})
        catalog_cache[catalog_id] = (
            catalog.get("FF_VIC_listino"),
            catalog.get("FF_Pers_TipoServizio")
        )
    except Exception:
        catalog_cache[catalog_id] = (None, None)
    return catalog_cache[catalog_id]


def get_row_catalog_id(row):
    for campo in ("catalogId", "productId", "idCatalog", "catalogProductId"):
        if row.get(campo):
            return row.get(campo)
    return None

def prefetch_companies_and_users(orders):

    '''
    precarica nella cache i dati di aziende e venditori (nome azienda, nome venditore) 
    in modo tale da non fare mille chiamate dopo dentro al loop
    '''
    company_ids = {o.get("crossId") for o in orders if o.get("crossId")}
    user_ids    = {o.get("salesPerson") for o in orders if o.get("salesPerson")}
    catalog_ids = {
        catalog_id
        for ordine in orders
        for row in ordine.get("rows", [])
        for catalog_id in [get_row_catalog_id(row)]
        if catalog_id
    }

    print(
        f"  Aziende uniche: {len(company_ids)} | Utenti unici: {len(user_ids)} | "
        f"Prodotti unici: {len(catalog_ids)}",
        flush=True
    )

    def fetch_company(cid):
        try:
            data = get_json(f"Company/{cid}")
            dati = (data.get("companyName"), data.get("vatId"), data.get("FF_VIC_ScalaSconti"), data.get("FF_VIC_TIPOREL"))
            return cid, dati
        except Exception:
            return cid, (None, None, None, None)

    def fetch_user(uid):
        '''
        legge dal server tutti i venditori e in base all'id utente dell'ordine
        restituisce il nome (alias) --> r.scimone, come serve a noi 
        '''
        try:
            account = get_json("Account/Get", {"id": uid})
            aliases = account.get("aliases") or []      #aliases è l'endpoint per avere r.scimone
            nome = aliases[0].upper() if aliases else None
            return uid, nome
        
        except Exception:
            return uid, None
        
    def fetch_catalog(caid):
        try:
            catalog = get_json("Catalog/Get", {"id":caid})
            dati = (
                catalog.get("FF_VIC_listino"),
                catalog.get("FF_Pers_TipoServizio")
            )
            return caid, dati
        except Exception:
            return caid, (None, None)
        
    '''
    così fai 5 chiamate in parallelo, in modo da leggere tutto il più veloce possibile ma senza sovraccaricare il server
    '''
    # max_workers=5 per non sovraccaricare il server
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fetch_company, cid) for cid in company_ids]
        for i, future in enumerate(as_completed(futures), 1):
            cid, result = future.result()
            company_cache[cid] = result
            print(f"  Aziende: {i}/{len(company_ids)}", end="\r", flush=True)

    print()
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fetch_user, uid) for uid in user_ids]
        for i, future in enumerate(as_completed(futures), 1):
            uid, result = future.result()
            user_cache[uid] = result
            print(f"  Utenti: {i}/{len(user_ids)}", end="\r", flush=True)

    print()
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fetch_catalog, caid) for caid in catalog_ids]
        for i, future in enumerate(as_completed(futures), 1):
            caid, result = future.result()
            catalog_cache[caid] = result
            print(f"  Prodotti: {i}/{len(catalog_ids)}", end="\r", flush=True)

    print("\n  Prefetch completato.", flush=True)


# ─── MAIN ─────────────────────────────────────────────────────
def main():
    print("=== Estrazione ordini CRM in Cloud ===\n")
    start_gara = time.perf_counter()

    print("1. Download ordini...")
    orders = get_all_orders()
    #print(f"   Totale: {len(orders)} ordini\n")

    inizio_gara, fine_gara, gara_corrente = trova_periodo_gara()
    orders, righe_totali, righe_filtrate = filtra_ordini_periodo_gara(
        orders,
        inizio_gara,
        fine_gara
    )
    print(
        f"   Filtro periodo gara {gara_corrente} "
        f"({inizio_gara.strftime('%d/%m/%Y')} - {fine_gara.strftime('%d/%m/%Y')})"
    )
    print(
        f"   Righe dopo filtro Data Attivazione: "
        f"{righe_filtrate}/{righe_totali} | Ordini rimasti: {len(orders)}\n"
    )

    print("2. Prefetch aziende, commerciali e prodotti...")
    prefetch_companies_and_users(orders)

    print("\n3. Elaborazione righe...")
    rows_out = []

    for i, o in enumerate(orders):

        '''I dati assegnati prima del ciclo sono tutti quelli che NON centrano con le RIGHE ORDINE'''
        
        azienda, piva, scala_sconti, tipo_relazione = get_company_info(o.get("crossId"))

        commerciale = get_user_name(o.get("salesPerson"))
        if commerciale == "BO":
            commerciale = "CRM My Way"

        stato           = STAGE_MAP.get(o.get("stage"), o.get("stage"))

        tipo_rel_maped  = TIPO_RELAZIONE_MAP[tipo_relazione]

        for row in o.get("rows", []):
            '''le asseegnazioni all'interno del ciclo sono RELATIVE alle RIGHE ORDINE'''

            codice_listino, codice_tipologia = get_catalog_info(get_row_catalog_id(row)) or (None, None)
            codice_listino = str(codice_listino) if codice_listino is not None else None
            codice_tipologia = str(codice_tipologia) if codice_tipologia is not None else None

            listino       = LISTINO_MAP.get(codice_listino, codice_listino)
            
            
            tip_servizio  = TIPOLOGIA_SERVIZIO_MAP.get(codice_tipologia, codice_tipologia)
            if tip_servizio == "EASYDEAL":
                tip_servizio = "EASY DEAL"

            rows_out.append({
                "Azienda":                    azienda,
                "Partita IVA":                piva,
                "ID Riga CRM":                row.get("id"),
                "ID Pratica":                 row.get("FF_VIC_ID_PRATICA"),
                "Stato ordine":               stato,
                "Prodotto":                   row.get("description"),
                "Tipologia servizio":         tip_servizio,
                "Quantità":                   int(row.get("qta")),
                "Prezzo unitario":            row.get("unitPrice"),
                "Prezzo finale":              row.get("totalPrice"),
                "Data creazione (Ordini)":    format_date(o.get("createdDate")),
                "Data Inserimento OmniSales": format_date(row.get("FF_VIC_OMNISALES")),
                "Data Passaggio ACA":         format_date(row.get("FF_VIC_ACA")),
                "Data Attivazione":           format_date(row.get("FF_VIC_ATTIVAZIONE")),
                "Commerciale di riferimento": commerciale,
                "ID CRM":                     f'TR4000{o.get("number")}',
                "Tipo Relazione":             tipo_rel_maped,
                "Listino":                    listino,
                "Scala sconti":               int(scala_sconti if scala_sconti not in ("", None) else 0),
            })

    print(f"   Righe generate: {len(rows_out)}\n")

    #print("4. Salvataggio Excel...")

    df = pd.DataFrame(rows_out, columns=[
        "Azienda", "Partita IVA", "ID Riga CRM", "ID Pratica", "Stato ordine",
        "Prodotto", "Tipologia servizio", "Quantità", "Prezzo unitario",
        "Prezzo finale", "Data creazione (Ordini)", "Data Inserimento OmniSales",
        "Data Passaggio ACA", "Data Attivazione", "Commerciale di riferimento",
        "ID CRM", "Tipo Relazione", "Listino", "Scala sconti"
    ])

    #output = "ordini_crm.xlsx"
    #df.to_excel(output, index=False)
    end_gara = time.perf_counter()

    #print(f"   Salvato: {output}\n")
    print(f"Tempo di esecuzione: {end_gara - start_gara:.2f} secondi")
    print("=== Fine caricamento dati ===\n")

    return df
