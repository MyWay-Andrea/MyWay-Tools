from __future__ import annotations

import base64
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

import requests

from config import (
    FCST_EMAIL_DESTINATARI,
    GRAPH_CLIENT_ID,
    GRAPH_CLIENT_SECRET,
    GRAPH_SENDER_EMAIL,
    GRAPH_TENANT_ID,
)


GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MESI = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]
CONTENT_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DIMENSIONE_MASSIMA_ALLEGATO = 3 * 1024 * 1024


def _verifica_configurazione(destinatari: list[str]) -> None:
    configurazione = {
        "GRAPH_CLIENT_ID": GRAPH_CLIENT_ID,
        "GRAPH_TENANT_ID": GRAPH_TENANT_ID,
        "GRAPH_CLIENT_SECRET": GRAPH_CLIENT_SECRET,
        "GRAPH_SENDER_EMAIL": GRAPH_SENDER_EMAIL,
    }
    mancanti = [nome for nome, valore in configurazione.items() if not valore]
    if mancanti:
        raise ValueError("Configurazione Microsoft Graph incompleta: " + ", ".join(mancanti))
    if not destinatari:
        raise ValueError("Nessun destinatario configurato per l'email FCST")


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


def _data_estesa(data: datetime) -> str:
    return f"{GIORNI[data.weekday()]} {data.day} {MESI[data.month - 1]} {data.year}"


def _euro(valore: float) -> str:
    testo = f"{float(valore):,.2f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _corpo_semplice(
    *,
    periodo: str,
    anno_breve: str,
    actual_mesi: dict[str, float],
    actual: float,
    da_inserire: float,
    in_attivazione: float,
    gara_potenziale: float,
    target: float,
    valore_missing: float,
    totale_opportunita: float,
) -> str:
    righe_mesi = "".join(
        f'<tr><td style="padding:7px 0;color:#667085;font-size:13px;">{escape(mese.upper())}</td>'
        f'<td align="right" style="padding:7px 0;color:#101828;font-size:13px;font-weight:bold;">{_euro(valore)}</td></tr>'
        for mese, valore in actual_mesi.items()
    )

    def riga(
        label: str,
        valore: float,
        *,
        evidenza: bool = False,
        rosso: bool = False,
        sottotitolo: str = "",
    ) -> str:
        sfondo = "#f0f7f2" if evidenza else "#ffffff"
        colore = "#b42318" if rosso else ("#1f5f3b" if evidenza else "#101828")
        colore_label = "#b42318" if rosso else ("#1f5f3b" if evidenza else "#667085")
        dimensione = "22px" if evidenza else "16px"
        dimensione_label = "14px" if evidenza else "12px"
        nota = (
            f'<div style="font-size:11px;line-height:16px;font-weight:normal;color:#667085;padding-top:4px;">{escape(sottotitolo)}</div>'
            if sottotitolo else ""
        )
        return (
            f'<tr><td colspan="2" height="8" style="font-size:0;line-height:0;">&nbsp;</td></tr>'
            f'<tr><td colspan="2" style="background:{sfondo};border:1px solid #e4e7ec;border-radius:14px;padding:17px 18px;">'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
            f'<td style="font-size:{dimensione_label};line-height:19px;font-weight:bold;color:{colore_label};letter-spacing:.5px;">{escape(label)}{nota}</td>'
            f'<td align="right" style="font-size:{dimensione};line-height:28px;font-weight:bold;color:{colore};white-space:nowrap;">{_euro(valore)}</td>'
            f'</tr></table></td></tr>'
        )

    return f"""<!doctype html>
    <html><body style="margin:0;padding:0;background-color:#f4f5f7;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f4f5f7;">
      <tr><td align="center" style="padding:24px 10px;">
        <table role="presentation" width="640" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:640px;background:#ffffff;border-radius:18px;font-family:Arial,Helvetica,sans-serif;color:#101828;">
          <tr><td style="padding:28px 30px 22px;border-bottom:4px solid #2e7031;">
            <div style="font-size:24px;line-height:31px;font-weight:bold;">Avanzamento gara</div>
            <div style="font-size:13px;line-height:20px;color:#667085;padding-top:5px;">{escape(periodo)} {anno_breve}</div>
          </td></tr>
          <tr><td style="padding:25px 30px 8px;font-size:14px;line-height:22px;color:#344054;">
            Ciao Giorgio,<br><br>in allegato troverai il file avanzamento gara relativo al trimestre <strong>{escape(periodo)} {anno_breve}</strong>.<br>Di seguito il riepilogo dei valori.
          </td></tr>
          <tr><td style="padding:10px 30px 28px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
              <tr><td colspan="2" style="background:#f8faf9;border:1px solid #e4e7ec;border-radius:14px;padding:18px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                  <tr><td style="font-size:14px;font-weight:bold;color:#2e7031;letter-spacing:.5px;">1. ACTUAL INFLOW</td><td align="right" style="font-size:25px;line-height:30px;font-weight:bold;color:#1f5f3b;">{_euro(actual)}</td></tr>
                  <tr><td colspan="2" style="padding-top:8px;"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">{righe_mesi}</table></td></tr>
                </table>
              </td></tr>
              {riga('2. DA INSERIRE', da_inserire)}
              {riga('2. IN ATTIVAZIONE', in_attivazione)}
              {riga('3. TOT GARA POTENZIALE', gara_potenziale, evidenza=True, sottotitolo='Actual + Da inserire + In attivazione')}
              {riga('4. TARGET', target)}
              {riga('5. VALORE MISSING', valore_missing, rosso=True)}
              {riga('6. TOTALE OPPORTUNITÀ INSERITE', totale_opportunita)}
            </table>
          </td></tr>
          <tr><td style="padding:20px 30px 28px;border-top:1px solid #e4e7ec;font-size:14px;line-height:22px;color:#475467;">Buon lavoro<br><strong style="color:#101828;">Reporting Team</strong></td></tr>
        </table>
      </td></tr>
    </table></body></html>"""


def invia_avanzamento_gara(
    contenuto_file: bytes,
    *,
    periodo: str,
    actual_mesi: dict[str, float],
    da_inserire: float,
    in_attivazione: float,
    target: float,
    totale_opportunita: float,
    destinatari: list[str] | None = None,
    nome_file: str = "FCST_G.MANDELLI.xlsx",
) -> None:
    destinatari_effettivi = destinatari or FCST_EMAIL_DESTINATARI
    _verifica_configurazione(destinatari_effettivi)
    if len(contenuto_file) >= DIMENSIONE_MASSIMA_ALLEGATO:
        raise ValueError("Il report FCST supera il limite di 3 MB per l'allegato diretto")

    oggi = datetime.today()
    oggetto = f"AVANZAMENTO GARA - {_data_estesa(oggi)}"
    nome_base = Path(nome_file).stem
    nome_allegato = f"{nome_base}_{oggi:%m%d_%H%M}.xlsx"
    anno_breve = str(oggi.year)[-2:]
    actual = sum(actual_mesi.values())
    ordini_rilasciati = da_inserire + in_attivazione
    gara_potenziale = actual + ordini_rilasciati
    valore_missing = target - gara_potenziale

    righe_actual = "".join(
        f'<tr><td style="padding:5px 0;color:#64748b;">{escape(mese.upper())}</td>'
        f'<td style="padding:5px 0;text-align:right;font-weight:700;color:#0f172a;">{_euro(valore)}</td></tr>'
        for mese, valore in actual_mesi.items()
    )
    corpo = f"""<!doctype html>
    <html><body style="margin:0;padding:0;background-color:#eef2f6;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#eef2f6;">
      <tr><td align="center" style="padding:28px 12px;">
        <table role="presentation" width="700" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:700px;font-family:Arial,Helvetica,sans-serif;color:#152238;">
          <tr><td style="background-color:#152238;border-radius:28px;padding:30px 32px;color:#ffffff;">
            <div style="font-size:11px;line-height:16px;font-weight:bold;letter-spacing:1.5px;color:#9fb3c8;">REPORTING TEAM · BUSINESS</div>
            <div style="font-size:28px;line-height:34px;font-weight:bold;padding-top:8px;">Avanzamento gara</div>
            <div style="font-size:14px;line-height:21px;color:#d9e2ec;padding-top:14px;">Ciao Giorgio,<br>in allegato troverai il file avanzamento gara relativo al trimestre <strong style="color:#ffffff;">{escape(periodo)} {anno_breve}</strong>.</div>
          </td></tr>
          <tr><td height="12" style="font-size:0;line-height:0;">&nbsp;</td></tr>
          <tr><td style="font-size:14px;line-height:20px;color:#52616f;padding:0 4px 4px;">Di seguito il sunto dei valori.</td></tr>
          <tr><td>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
              <tr>
                <td width="59%" valign="top" style="background-color:#e8f7ef;border:1px solid #d3efdf;border-radius:24px;padding:24px;">
                  <div style="font-size:11px;line-height:16px;font-weight:bold;letter-spacing:1.2px;color:#087a55;">01 · ACTUAL INFLOW</div>
                  <div style="font-size:31px;line-height:38px;font-weight:bold;padding:7px 0 13px;color:#11352a;">{_euro(actual)}</div>
                  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="font-size:13px;line-height:18px;">{righe_actual}</table>
                </td>
                <td width="12" style="font-size:0;line-height:0;">&nbsp;</td>
                <td width="39%" valign="top" style="background-color:#eaf2ff;border:1px solid #d8e6ff;border-radius:24px;padding:24px;">
                  <div style="font-size:11px;line-height:16px;font-weight:bold;letter-spacing:1.2px;color:#2855a6;">02 · ORDINI RILASCIATI</div>
                  <div style="font-size:25px;line-height:32px;font-weight:bold;padding:7px 0 15px;color:#17335f;">{_euro(ordini_rilasciati)}</div>
                  <div style="font-size:10px;line-height:15px;color:#61758a;">DA INSERIRE</div>
                  <div style="font-size:16px;line-height:22px;font-weight:bold;color:#17335f;padding-bottom:11px;">{_euro(da_inserire)}</div>
                  <div style="font-size:10px;line-height:15px;color:#61758a;">IN ATTIVAZIONE</div>
                  <div style="font-size:16px;line-height:22px;font-weight:bold;color:#17335f;">{_euro(in_attivazione)}</div>
                </td>
              </tr>
            </table>
          </td></tr>
          <tr><td height="12" style="font-size:0;line-height:0;">&nbsp;</td></tr>
          <tr><td style="background-color:#fff0dc;border:1px solid #ffe2bd;border-radius:24px;padding:25px 28px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
              <td valign="middle"><div style="font-size:11px;line-height:16px;font-weight:bold;letter-spacing:1.2px;color:#a64b16;">03 · TOT GARA POTENZIALE</div><div style="font-size:12px;line-height:18px;color:#9a5c37;padding-top:5px;">Actual inflow + ordini rilasciati</div></td>
              <td valign="middle" align="right" style="font-size:32px;line-height:38px;font-weight:bold;color:#542a13;white-space:nowrap;">{_euro(gara_potenziale)}</td>
            </tr></table>
          </td></tr>
          <tr><td height="12" style="font-size:0;line-height:0;">&nbsp;</td></tr>
          <tr><td>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
              <td width="49%" valign="top" style="background-color:#f0ecff;border:1px solid #e2dbff;border-radius:24px;padding:24px;">
                <div style="font-size:11px;line-height:16px;font-weight:bold;letter-spacing:1.2px;color:#6745b5;">04 · TARGET</div><div style="font-size:27px;line-height:34px;font-weight:bold;color:#39236d;padding-top:8px;">{_euro(target)}</div>
              </td>
              <td width="12" style="font-size:0;line-height:0;">&nbsp;</td>
              <td width="49%" valign="top" style="background-color:#ffebed;border:1px solid #ffd7dc;border-radius:24px;padding:24px;">
                <div style="font-size:11px;line-height:16px;font-weight:bold;letter-spacing:1.2px;color:#b22d42;">05 · VALORE MISSING</div><div style="font-size:27px;line-height:34px;font-weight:bold;color:#721c2b;padding-top:8px;">{_euro(valore_missing)}</div><div style="font-size:11px;line-height:16px;color:#9d5360;padding-top:4px;">Target − gara potenziale</div>
              </td>
            </tr></table>
          </td></tr>
          <tr><td height="12" style="font-size:0;line-height:0;">&nbsp;</td></tr>
          <tr><td style="background-color:#e5f7f8;border:1px solid #cfedef;border-radius:24px;padding:24px 28px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td style="font-size:11px;line-height:16px;font-weight:bold;letter-spacing:1.2px;color:#18727a;">06 · TOTALE OPPORTUNITÀ INSERITE</td><td align="right" style="font-size:28px;line-height:34px;font-weight:bold;color:#164e54;white-space:nowrap;">{_euro(totale_opportunita)}</td></tr></table>
          </td></tr>
          <tr><td style="padding:25px 8px 6px;font-size:14px;line-height:21px;color:#52616f;">Buon lavoro<br><strong style="color:#152238;">Reporting Team</strong></td></tr>
        </table>
      </td></tr>
    </table></body></html>"""
    corpo = _corpo_semplice(
        periodo=periodo,
        anno_breve=anno_breve,
        actual_mesi=actual_mesi,
        actual=actual,
        da_inserire=da_inserire,
        in_attivazione=in_attivazione,
        gara_potenziale=gara_potenziale,
        target=target,
        valore_missing=valore_missing,
        totale_opportunita=totale_opportunita,
    )
    payload = {
        "message": {
            "subject": oggetto,
            "body": {"contentType": "HTML", "content": corpo},
            "toRecipients": [
                {"emailAddress": {"address": indirizzo}}
                for indirizzo in destinatari_effettivi
            ],
            "attachments": [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": nome_allegato,
                "contentType": CONTENT_TYPE_XLSX,
                "contentBytes": base64.b64encode(contenuto_file).decode("ascii"),
            }],
        },
        "saveToSentItems": True,
    }
    mittente = quote(GRAPH_SENDER_EMAIL, safe="")
    risposta = requests.post(
        f"https://graph.microsoft.com/v1.0/users/{mittente}/sendMail",
        headers={
            "Authorization": f"Bearer {_token_graph()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    risposta.raise_for_status()
    print(f"Email FCST inviata a: {', '.join(destinatari_effettivi)}")
