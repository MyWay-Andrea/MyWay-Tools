from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests

from config import (
    EMAIL_DESTINATARI,
    GRAPH_CLIENT_ID,
    GRAPH_CLIENT_SECRET,
    GRAPH_SENDER_EMAIL,
    GRAPH_TENANT_ID,
    TEST_RUN,
)


DIMENSIONE_MASSIMA_ALLEGATO = 3 * 1024 * 1024


def _verifica_configurazione() -> None:
    configurazione = {
        "GRAPH_CLIENT_ID": GRAPH_CLIENT_ID,
        "GRAPH_TENANT_ID": GRAPH_TENANT_ID,
        "GRAPH_CLIENT_SECRET": GRAPH_CLIENT_SECRET,
        "GRAPH_SENDER_EMAIL": GRAPH_SENDER_EMAIL,
    }
    mancanti = [nome for nome, valore in configurazione.items() if not valore]
    if mancanti:
        raise ValueError(
            "Configurazione Microsoft Graph incompleta: " + ", ".join(mancanti)
        )
    if not EMAIL_DESTINATARI:
        raise ValueError("Nessun destinatario configurato in CONSUMER_EMAIL_DESTINATARI")


def _token_graph() -> str:
    risposta = requests.post(
        f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token",
        data={
            "client_id": GRAPH_CLIENT_ID,
            "client_secret": GRAPH_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=30,
    )
    risposta.raise_for_status()
    token = risposta.json().get("access_token")
    if not token:
        raise ValueError("Microsoft Graph non ha restituito un access token")
    return token


def invia_report(
    file_report: Path,
    periodo: tuple[datetime, datetime],
) -> bool:
    """Allega il report XLSX e lo invia tramite Microsoft Graph."""
    file_report = Path(file_report)
    if not file_report.is_file():
        raise FileNotFoundError(f"Report da allegare non trovato: {file_report}")
    if file_report.stat().st_size >= DIMENSIONE_MASSIMA_ALLEGATO:
        raise ValueError(
            "Il report supera il limite di 3 MB per l'allegato diretto; "
            "serve una upload session Microsoft Graph"
        )

    inizio, fine = periodo
    periodo_testo = f"{inizio:%d/%m/%Y} - {fine:%d/%m/%Y}"
    oggetto = f"Tracciamento Consumer {periodo_testo}"
    corpo = (
        "<p>Buongiorno,</p>"
        "<p>in allegato il <strong>Cruscotto Piste Consumer</strong> "
        f"relativo al periodo <strong>{periodo_testo}</strong>.</p>"
        "<p>Il file riepiloga per ciascun negozio i risultati in pezzi e punti "
        "delle piste:</p>"
        "<ul>"
        "<li>Mobile</li>"
        "<li>Wireline</li>"
        "<li>Upselling</li>"
        "<li>Energy</li>"
        "<li>Commissionali</li>"
        "</ul>"
        "<p>Cordiali saluti</p>"
        "<p>Reportistica MyWay</p>"
    )

    if TEST_RUN:
        print("TEST RUN: nessun messaggio inviato")
        print(f"Mittente: {GRAPH_SENDER_EMAIL or '[non configurato]'}")
        print(f"Destinatari: {', '.join(EMAIL_DESTINATARI) or '[non configurati]'}")
        print(f"Oggetto: {oggetto}")
        print(f"Allegato: {file_report}")
        return False

    _verifica_configurazione()
    payload = {
        "message": {
            "subject": oggetto,
            "body": {"contentType": "HTML", "content": corpo},
            "toRecipients": [
                {"emailAddress": {"address": indirizzo}}
                for indirizzo in EMAIL_DESTINATARI
            ],
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": file_report.name,
                    "contentType": (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    "contentBytes": base64.b64encode(
                        file_report.read_bytes()
                    ).decode("ascii"),
                }
            ],
        },
        "saveToSentItems": True,
    }
    token = _token_graph()
    mittente = quote(GRAPH_SENDER_EMAIL, safe="")
    risposta = requests.post(
        f"https://graph.microsoft.com/v1.0/users/{mittente}/sendMail",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    risposta.raise_for_status()
    print(f"Email inviata a: {', '.join(EMAIL_DESTINATARI)}")
    return True
