from __future__ import annotations

import base64
from urllib.parse import quote

import requests

from config import (
    GRAPH_CLIENT_ID,
    GRAPH_CLIENT_SECRET,
    GRAPH_SENDER_EMAIL,
    GRAPH_TENANT_ID,
    LOGO_PATH,
)


def _verifica_configurazione() -> None:
    valori = {
        "GRAPH_CLIENT_ID": GRAPH_CLIENT_ID,
        "GRAPH_TENANT_ID": GRAPH_TENANT_ID,
        "GRAPH_CLIENT_SECRET": GRAPH_CLIENT_SECRET,
        "GRAPH_SENDER_EMAIL": GRAPH_SENDER_EMAIL,
    }
    mancanti = [nome for nome, valore in valori.items() if not valore]
    if mancanti:
        raise RuntimeError("Configurazione Graph incompleta: " + ", ".join(mancanti))


def _token() -> str:
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
    if not risposta.ok:
        raise RuntimeError(f"Autenticazione Graph fallita (HTTP {risposta.status_code})")
    token = risposta.json().get("access_token")
    if not token:
        raise RuntimeError("Microsoft Graph non ha restituito un access token")
    return token


def invia_html(*, destinatario: str, oggetto: str, html: str) -> None:
    _verifica_configurazione()
    if not LOGO_PATH.is_file():
        raise RuntimeError(f"Logo non trovato: {LOGO_PATH.name}")
    payload = {
        "message": {
            "subject": oggetto,
            "body": {"contentType": "HTML", "content": html},
            "toRecipients": [{"emailAddress": {"address": destinatario}}],
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": LOGO_PATH.name,
                    "contentType": "image/jpeg",
                    "contentBytes": base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii"),
                    "isInline": True,
                    "contentId": "logo-mwr",
                }
            ],
        },
        "saveToSentItems": True,
    }
    mittente = quote(GRAPH_SENDER_EMAIL, safe="")
    risposta = requests.post(
        f"https://graph.microsoft.com/v1.0/users/{mittente}/sendMail",
        headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if not risposta.ok:
        raise RuntimeError(f"Invio Graph fallito (HTTP {risposta.status_code})")

