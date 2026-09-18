import time
from datetime import datetime
from pathlib import Path

import requests

from config import API_KEY, BASE_URL, CRM_DRY_RUN
from console import avviso, errore as errore_console, info, successo
from crm_anagrafica import estrai_aziende, get_json


session = requests.Session()
TENTATIVI = 5
TIMEOUT = 30
ENDPOINT_AZIENDE = "Company/CreateOrUpdate"
_FILE_AVANZAMENTO_CORRENTE = None


def _nascondi_api_key(valore) -> str:
    testo = str(valore)

    if API_KEY:
        testo = testo.replace(API_KEY, "***")

    return testo


def _formatta_durata(secondi: float) -> str:
    secondi_interi = max(0, int(secondi))
    ore, resto = divmod(secondi_interi, 3600)
    minuti, secondi_residui = divmod(resto, 60)
    return f"{ore:02d}:{minuti:02d}:{secondi_residui:02d}"


def _scrivi_avanzamento(messaggio: str) -> None:
    if _FILE_AVANZAMENTO_CORRENTE is None:
        return

    timestamp = datetime.now().isoformat(timespec="seconds")

    # Apertura e chiusura a ogni riga: il contenuto resta su disco
    # anche in caso di interruzione improvvisa del programma.
    with _FILE_AVANZAMENTO_CORRENTE.open(
        "a",
        encoding="utf-8",
    ) as file_log:
        file_log.write(f"{timestamp} | {messaggio}\n")


def _separa_operazioni_avanzamento() -> None:
    print()

    if _FILE_AVANZAMENTO_CORRENTE is None:
        return

    with _FILE_AVANZAMENTO_CORRENTE.open(
        "a",
        encoding="utf-8",
    ) as file_log:
        file_log.write("\n")


def _prepara_log_avanzamento(cartella: Path, totale: int) -> Path:
    global _FILE_AVANZAMENTO_CORRENTE

    cartella_log = Path(cartella) / "LOG"
    cartella_log.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _FILE_AVANZAMENTO_CORRENTE = (
        cartella_log / f"CRM_AVANZAMENTO_{timestamp}.txt"
    )
    modalita = "SIMULAZIONE" if CRM_DRY_RUN else "REALE"
    _scrivi_avanzamento(
        f"AVVIO | modalità={modalita} | operazioni_previste={totale}"
    )
    info(f"Log avanzamento CRM: {_FILE_AVANZAMENTO_CORRENTE}")
    return _FILE_AVANZAMENTO_CORRENTE


def _stato_http(errore):
    risposta = getattr(errore, "response", None)
    return getattr(risposta, "status_code", None)


def _errore_autorizzazione(errore) -> bool:
    return _stato_http(errore) in {401, 403}


def _deve_ritentare(errore) -> bool:
    if isinstance(
        errore,
        (requests.Timeout, requests.ConnectionError),
    ):
        return True

    stato = _stato_http(errore)

    if stato is None:
        return True

    return stato in {408, 425, 429} or 500 <= stato <= 599


def _richiesta_json(metodo: str, endpoint: str, payload: dict) -> dict:
    if not API_KEY:
        raise ValueError(
            "Chiave API mancante: configura la variabile d'ambiente "
            "CRM_REPORTISTICA_API_KEY_CB"
        )

    url = f"{BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    invia = getattr(session, metodo.lower())

    for tentativo in range(1, TENTATIVI + 1):
        try:
            risposta = invia(
                url,
                params={"apikey": API_KEY},
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=TIMEOUT,
            )
            risposta.raise_for_status()
            return risposta.json()
        except requests.RequestException as errore_richiesta:
            if (
                tentativo == TENTATIVI
                or not _deve_ritentare(errore_richiesta)
            ):
                raise

            attesa = 5 * tentativo
            messaggio = (
                f"RETRY API | endpoint={endpoint} | "
                f"tentativo={tentativo}/{TENTATIVI} | "
                f"nuovo_tentativo_tra={attesa}s | "
                f"errore={_nascondi_api_key(errore_richiesta)}"
            )
            avviso(messaggio)
            _scrivi_avanzamento(messaggio)
            time.sleep(attesa)

    raise RuntimeError("Richiesta CRM non completata")


def post_json(endpoint: str, payload: dict) -> dict:
    return _richiesta_json("POST", endpoint, payload)


def put_json(endpoint: str, payload: dict) -> dict:
    return _richiesta_json("PUT", endpoint, payload)


def _rimuovi_campi_vuoti(payload: dict) -> dict:
    return {
        chiave: valore
        for chiave, valore in payload.items()
        if valore is not None and valore != ""
    }


def _aggiungi_email(payload: dict, dati: dict) -> None:
    """Aggiunge l'e-mail CB nel formato atteso dal CRM, se valorizzata."""
    email = str(dati.get("email") or "").strip()

    # "N/A" è il segnaposto usato nel report quando il CB non ha il campo.
    # In tal caso omettere il campo preserva l'e-mail già presente nel CRM.
    if email and email != "N/A":
        payload["emails"] = [{"value": email}]


def _commerciale_id(dati: dict) -> int:
    valore = dati.get("commerciale_id")

    if valore is None:
        valore = dati.get("nuovo_sales_person_id")

    if valore is None:
        raise ValueError("ID commerciale mancante")

    try:
        return int(valore)
    except (TypeError, ValueError) as errore:
        raise ValueError(
            f"ID commerciale non numerico: {valore!r}"
        ) from errore


def crea_azienda_crm(dati: dict) -> dict:
    payload = {
        "companyName": dati["ragione_sociale"],
        "vatId": dati.get("partita_iva", ""),
        "FF_VIC_CUSTCODE": dati.get("custcode", ""),
        "salesPersons": [_commerciale_id(dati)],
    }
    payload.update(dati.get("consistenze") or {})
    _aggiungi_email(payload, dati)

    return post_json(
        ENDPOINT_AZIENDE,
        _rimuovi_campi_vuoti(payload),
    )


def aggiorna_azienda_crm(azienda_id: str, dati: dict) -> dict:
    payload = {"id": azienda_id}

    if dati.get("aggiorna_commerciale", True):
        payload["salesPersons"] = [_commerciale_id(dati)]

    payload.update(dati.get("consistenze") or {})
    _aggiungi_email(payload, dati)

    return post_json(
        ENDPOINT_AZIENDE,
        _rimuovi_campi_vuoti(payload),
    )


def _dettaglio_errore(errore: Exception) -> str:
    risposta = getattr(errore, "response", None)

    if risposta is not None:
        try:
            corpo = risposta.json()
        except ValueError:
            corpo = risposta.text

        if corpo:
            return _nascondi_api_key(f"{errore} - {corpo}")

    return _nascondi_api_key(errore)


def _errore_duplicato(errore: Exception) -> bool:
    return "duplic" in _dettaglio_errore(errore).lower()


def _escape_odata(valore) -> str:
    return str(valore).replace("'", "''")


def _trova_id_azienda_esistente(dati: dict):
    filtri = []

    if dati.get("partita_iva"):
        filtri.append(
            f"vatId eq '{_escape_odata(dati['partita_iva'])}'"
        )

    if dati.get("custcode"):
        filtri.append(
            "FF_VIC_CUSTCODE eq "
            f"'{_escape_odata(dati['custcode'])}'"
        )

    for filtro in filtri:
        risposta = get_json(
            "Company/Search",
            {"$filter": filtro, "$top": 2},
        )
        aziende = estrai_aziende(risposta)

        if len(aziende) == 1 and aziende[0].get("id") is not None:
            return aziende[0]["id"]

    return None


def _estrai_id_risposta(risposta):
    if isinstance(risposta, (int, str)):
        return risposta

    if isinstance(risposta, dict):
        for chiave in ("id", "companyId"):
            if risposta.get(chiave) is not None:
                return risposta[chiave]

        dati = risposta.get("data")
        if isinstance(dati, dict):
            return dati.get("id") or dati.get("companyId")
        if isinstance(dati, (int, str)):
            return dati

    return None


def _crea_log(
    dati: dict,
    azione: str,
    esito: str,
    dettaglio,
    azienda_crm_id=None,
) -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "azione": azione,
        "stato_analisi": dati.get("stato"),
        "azienda_crm_id": azienda_crm_id,
        "ragione_sociale": dati.get("ragione_sociale"),
        "commerciale": dati.get("commerciale"),
        "esito": esito,
        "dettaglio": dettaglio,
    }


def esegui_operazioni_su_crm(
    analisi: dict,
    cartella_log=None,
) -> list[dict]:
    log_entries = []
    stati_operativi = {
        "da_creare",
        "da_riassegnare",
        "presente_corretta",
    }
    operazioni = [
        dati
        for dati in analisi.get("risultati", [])
        if dati.get("stato") in stati_operativi
    ]
    totale = len(operazioni)
    inizio_totale = time.monotonic()
    bloccato_autorizzazione = False

    if cartella_log is not None:
        _prepara_log_avanzamento(Path(cartella_log), totale)

    if totale == 0:
        messaggio = "FINE | nessuna operazione CRM da eseguire"
        info(messaggio)
        _scrivi_avanzamento(messaggio)
        return log_entries

    for indice, dati in enumerate(operazioni, start=1):
        if indice > 1:
            _separa_operazioni_avanzamento()

        stato = dati.get("stato")
        azienda_crm_id = dati.get("azienda_crm_id")
        ragione_sociale = (
            dati.get("ragione_sociale") or "Azienda senza nome"
        )
        percentuale = indice / totale * 100
        trascorso_prima = time.monotonic() - inizio_totale

        if indice == 1:
            eta_prima = "calcolo in corso"
        else:
            media_prima = trascorso_prima / (indice - 1)
            eta_prima = _formatta_durata(
                media_prima * (totale - indice + 1)
            )

        prefisso = f"[{indice}/{totale} | {percentuale:5.1f}%]"
        messaggio_inizio = (
            f"{prefisso} INIZIO | stato={stato} | "
            f"azienda={ragione_sociale} | "
            f"trascorso={_formatta_durata(trascorso_prima)} | "
            f"stimato={eta_prima}"
        )
        info(messaggio_inizio)
        _scrivi_avanzamento(messaggio_inizio)
        inizio_operazione = time.monotonic()

        try:
            if CRM_DRY_RUN:
                risposta = "Nessuna chiamata API effettuata"
                azione = "DRY-RUN"
                esito = "OK (simulato)"
            elif stato == "da_creare":
                try:
                    risposta = crea_azienda_crm(dati)
                    azienda_crm_id = (
                        _estrai_id_risposta(risposta)
                        or azienda_crm_id
                    )
                    azione = "CREAZIONE"
                except requests.RequestException as errore_creazione:
                    if not _errore_duplicato(errore_creazione):
                        raise

                    azienda_crm_id = _trova_id_azienda_esistente(dati)
                    if azienda_crm_id is None:
                        raise

                    risposta = aggiorna_azienda_crm(
                        azienda_crm_id,
                        dati,
                    )
                    azione = "AGGIORNAMENTO"
            else:
                if azienda_crm_id is None:
                    raise ValueError("ID azienda CRM mancante")

                dati_invio = dict(dati)
                dati_invio["aggiorna_commerciale"] = (
                    stato == "da_riassegnare"
                )
                risposta = aggiorna_azienda_crm(
                    azienda_crm_id,
                    dati_invio,
                )
                azione = "AGGIORNAMENTO"
                esito = "OK"

            if not CRM_DRY_RUN and stato == "da_creare":
                esito = "OK"

            log_entry = _crea_log(
                dati,
                azione,
                esito,
                risposta,
                azienda_crm_id,
            )
            log_entries.append(log_entry)
            durata_operazione = time.monotonic() - inizio_operazione
            trascorso = time.monotonic() - inizio_totale
            eta = _formatta_durata(
                trascorso / indice * (totale - indice)
            )
            messaggio_esito = (
                f"{prefisso} {esito} | azione={azione} | "
                f"azienda={ragione_sociale} | "
                f"durata={_formatta_durata(durata_operazione)} | "
                f"trascorso={_formatta_durata(trascorso)} | stimato={eta}"
            )
            successo(messaggio_esito)
            _scrivi_avanzamento(messaggio_esito)
        except KeyboardInterrupt:
            durata_operazione = time.monotonic() - inizio_operazione
            messaggio_interruzione = (
                f"{prefisso} INTERROTTO DALL'UTENTE | "
                f"azienda={ragione_sociale} | "
                f"durata={_formatta_durata(durata_operazione)}"
            )
            avviso(messaggio_interruzione)
            _scrivi_avanzamento(messaggio_interruzione)
            raise
        except Exception as eccezione:
            dettaglio_eccezione = _dettaglio_errore(eccezione)
            log_entry = _crea_log(
                dati,
                "ERRORE",
                "FALLITO",
                dettaglio_eccezione,
                azienda_crm_id,
            )
            log_entries.append(log_entry)
            durata_operazione = time.monotonic() - inizio_operazione
            trascorso = time.monotonic() - inizio_totale
            eta = _formatta_durata(
                trascorso / indice * (totale - indice)
            )
            messaggio_esito = (
                f"{prefisso} FALLITO | azienda={ragione_sociale} | "
                f"durata={_formatta_durata(durata_operazione)} | "
                f"trascorso={_formatta_durata(trascorso)} | "
                f"stimato={eta} | "
                f"errore={dettaglio_eccezione}"
            )
            errore_console(messaggio_esito)
            _scrivi_avanzamento(messaggio_esito)

            if _errore_autorizzazione(eccezione):
                bloccato_autorizzazione = True
                messaggio_blocco = (
                    "BLOCCO LOTTO | autorizzazione CRM negata | "
                    "le operazioni successive non verranno tentate"
                )
                errore_console(messaggio_blocco)
                _scrivi_avanzamento(messaggio_blocco)
                break

    durata_totale = time.monotonic() - inizio_totale
    successi = sum(
        1
        for voce in log_entries
        if voce["esito"].startswith("OK")
    )
    falliti = sum(
        1
        for voce in log_entries
        if voce["esito"] == "FALLITO"
    )
    messaggio_fine = (
        f"FINE | completate={len(log_entries)}/{totale} | "
        f"successi={successi} | falliti={falliti} | "
        f"blocco_autorizzazione={bloccato_autorizzazione} | "
        f"durata_totale={_formatta_durata(durata_totale)}"
    )
    info(messaggio_fine)
    _scrivi_avanzamento(messaggio_fine)
    return log_entries
