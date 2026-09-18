import time
from datetime import datetime
from io import BytesIO

import pandas as pd
from colorama import Fore, init

from config import (
    COLONNE_OUTPUT_GARA,
    LISTINO_MAP,
    PATH_BASI_DATI,
    PERIODO_GARE,
    STAGE_MAP,
    TIPOLOGIA_SERVIZIO_MAP,
    TIPO_RELAZIONE_MAP,
    _formatta_excel,
    carica_file_sharepoint,
)
from estrai_gara_API import (
    filtra_ordini_periodo_gara,
    format_date,
    get_all_orders,
    get_catalog_info,
    get_company_info,
    get_row_catalog_id,
    get_user_name,
    prefetch_companies_and_users,
)
from formatta_gara import formatta_colonne

init(autoreset=True)


def trova_periodo_gara_precedente():
    oggi = datetime.today()
    anno = oggi.year
    gara_corrente = PERIODO_GARE[oggi.month]

    periodi = [
        ("Gen - Mar", 1, 1, 3, 31),
        ("Apr - Giu", 4, 1, 6, 30),
        ("Lug - Set", 7, 1, 9, 30),
        ("Ott - Dic", 10, 1, 12, 31),
    ]

    indice_corrente = next(
        i for i, periodo in enumerate(periodi)
        if periodo[0] == gara_corrente
    )
    indice_precedente = indice_corrente - 1
    anno_precedente = anno

    if indice_precedente < 0:
        indice_precedente = len(periodi) - 1
        anno_precedente -= 1

    nome_periodo, mese_inizio, giorno_inizio, mese_fine, giorno_fine = periodi[indice_precedente]
    inizio_gara = datetime(anno_precedente, mese_inizio, giorno_inizio).date()
    fine_gara = datetime(anno_precedente, mese_fine, giorno_fine).date()

    return inizio_gara, fine_gara, nome_periodo, anno_precedente


def nome_file_chiusura(periodo, anno):
    periodo_file = periodo.replace(" ", "").replace("-", "_")
    return f"CHIUSURA_GARA_{anno}_{periodo_file}.xlsx"


def crea_df_ordini_chiusura(orders):
    rows_out = []

    for ordine in orders:
        azienda, piva, scala_sconti, tipo_relazione = get_company_info(ordine.get("crossId"))

        commerciale = get_user_name(ordine.get("salesPerson"))
        if commerciale == "BO":
            commerciale = "CRM My Way"

        stato = STAGE_MAP.get(ordine.get("stage"), ordine.get("stage"))
        tipo_rel_maped = TIPO_RELAZIONE_MAP.get(tipo_relazione, tipo_relazione)

        for row in ordine.get("rows", []):
            codice_listino, codice_tipologia = get_catalog_info(get_row_catalog_id(row)) or (None, None)
            codice_listino = str(codice_listino) if codice_listino is not None else None
            codice_tipologia = str(codice_tipologia) if codice_tipologia is not None else None

            listino = LISTINO_MAP.get(codice_listino, codice_listino)
            tip_servizio = TIPOLOGIA_SERVIZIO_MAP.get(codice_tipologia, codice_tipologia)
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
                "Quantita":                   int(row.get("qta")),
                "Prezzo unitario":            row.get("unitPrice"),
                "Prezzo finale":              row.get("totalPrice"),
                "Data creazione (Ordini)":    format_date(ordine.get("createdDate")),
                "Data Inserimento OmniSales": format_date(row.get("FF_VIC_OMNISALES")),
                "Data Passaggio ACA":         format_date(row.get("FF_VIC_ACA")),
                "Data Attivazione":           format_date(row.get("FF_VIC_ATTIVAZIONE")),
                "Commerciale di riferimento": commerciale,
                "ID CRM":                     f"TR4000{ordine.get('number')}",
                "Tipo Relazione":             tipo_rel_maped,
                "Listino":                    listino,
                "Scala sconti":               int(scala_sconti if scala_sconti not in ("", None) else 0),
            })

    return pd.DataFrame(rows_out)


def main():
    print("=== Chiusura gara CRM in Cloud ===\n")
    start = time.perf_counter()

    inizio_gara, fine_gara, periodo, anno = trova_periodo_gara_precedente()
    print(
        f"Periodo chiusura gara: {periodo} "
        f"({inizio_gara.strftime('%d/%m/%Y')} - {fine_gara.strftime('%d/%m/%Y')})\n"
    )

    print("1. Download ordini...")
    orders = get_all_orders()

    orders, righe_totali, righe_filtrate = filtra_ordini_periodo_gara(
        orders,
        inizio_gara,
        fine_gara
    )
    print(
        f"   Righe con Data Attivazione nel periodo: "
        f"{righe_filtrate}/{righe_totali} | Ordini rimasti: {len(orders)}\n"
    )

    print("2. Prefetch aziende, commerciali e prodotti...")
    prefetch_companies_and_users(orders)

    print("\n3. Elaborazione righe...")
    df = crea_df_ordini_chiusura(orders)
    print(f"   Righe generate: {len(df)}\n")

    print("4. Formattazione e salvataggio...")
    df_formattato = formatta_colonne(df)
    df_formattato = df_formattato[df_formattato["Stato Ordine"] == "Attivato"].copy()
    df_output = df_formattato[COLONNE_OUTPUT_GARA]

    nome_output = nome_file_chiusura(periodo, anno)
    buffer = BytesIO()
    df_output.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    _formatta_excel(buffer)
    caricato = carica_file_sharepoint(
        PATH_BASI_DATI,
        nome_output,
        buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    print(Fore.GREEN + f"File salvato: {caricato.get('webUrl', nome_output)}")
    print(f"Tempo di esecuzione: {time.perf_counter() - start:.2f} secondi")
    print("=== Fine chiusura gara ===\n")

    return df_output


if __name__ == "__main__":
    main()
