from __future__ import annotations

import os
import shutil
import subprocess
from datetime import date, datetime
from html import escape
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
MJML_CLI = PROJECT_DIR / "node_modules" / "mjml" / "bin" / "mjml"
CRM_TODAY_URL = "https://app.crmincloud.it/today"


def _testo(valore: object, fallback: str = "Non indicato") -> str:
    if valore is None or str(valore).strip() == "":
        return fallback
    return escape(str(valore))


def _data(valore: object) -> str:
    return valore.strftime("%d/%m/%Y") if isinstance(valore, (date, datetime)) else "Data non valida"


def _righe_opportunita(elementi: list[dict]) -> str:
    return "".join(
        "<tr>"
        f'<td class="cell client">{_testo(item.get("cliente"), "Cliente non disponibile")}</td>'
        f'<td class="cell">{_testo(item.get("prodotto"))}</td>'
        f'<td class="cell nowrap">{_testo(item.get("codice"))}</td>'
        f'<td class="cell nowrap">{_data(item.get("data_chiusura"))}</td>'
        "</tr>"
        for item in elementi
    )


def _righe_appuntamenti(elementi: list[dict]) -> str:
    return "".join(
        "<tr>"
        f'<td class="cell client">{_testo(item.get("cliente"), "Cliente non disponibile")}</td>'
        f'<td class="cell nowrap">{_data(item.get("data"))}</td>'
        f'<td class="cell">{_testo(item.get("tipo"))}</td>'
        "</tr>"
        for item in elementi
    )


def _sezione(titolo: str, azione: str, elementi: list[dict], *, tipo: str) -> str:
    if not elementi:
        return ""
    if tipo == "opportunita":
        badge_color = "#B5121B"
        barra, classe = "#D7192D", "opportunity-table"
        intestazione = "<tr><th>Cliente</th><th>Prodotto</th><th>Codice</th><th>Chiusura prevista</th></tr>"
        righe = _righe_opportunita(elementi)
    else:
        badge_color = "#075A9C"
        barra, classe = "#1677B8", "appointment-table"
        intestazione = "<tr><th>Cliente</th><th>Data</th><th>Tipo</th></tr>"
        righe = _righe_appuntamenti(elementi)
    return f"""
      <mj-section background-color="#FFFFFF" border="1px solid #E3E6E8" border-top="3px solid {barra}" border-radius="10px" padding="16px 18px 14px">
        <mj-column padding="0">
          <mj-table padding="0 0 5px" css-class="card-heading">
            <tr>
              <td style="font-size:17px;line-height:23px;font-weight:700;color:#17191C;">{escape(titolo)}</td>
              <td align="right" style="font-size:11px;font-weight:700;color:{badge_color};white-space:nowrap;">{len(elementi)} ELEMENTI</td>
            </tr>
          </mj-table>
          <mj-text padding="0 0 12px" font-size="12px" line-height="18px" color="#5F6368">{escape(azione)}</mj-text>
          <mj-table padding="0" css-class="{classe}">{intestazione}{righe}</mj-table>
        </mj-column>
      </mj-section>
      <mj-section padding="7px 0"><mj-column padding="0"><mj-spacer height="1px" /></mj-column></mj-section>
    """


def _riepilogo_bento(sezioni: dict[str, list[dict]]) -> str:
    opportunita = len(sezioni["opportunita_scadute"])
    appuntamenti = len(sezioni["appuntamenti_arretrati"]) + len(sezioni["appuntamenti_oggi"])
    return f"""
    <mj-section padding="0">
      <mj-column width="49%" background-color="#FFF6F7" border="1px solid #F2D8DC" border-top="5px solid #D7192D" border-radius="16px" padding="20px 22px">
        <mj-text padding="0" font-size="12px" line-height="18px" font-weight="700" color="#B5121B" letter-spacing=".7px">OPPORTUNITÀ</mj-text>
        <mj-text padding="6px 0 2px" font-size="32px" line-height="38px" font-weight="700" color="#8F101E">{opportunita}</mj-text>
        <mj-text padding="0" font-size="13px" line-height="19px" color="#6B4A4E">record da verificare</mj-text>
      </mj-column>
      <mj-column width="2%" padding="0"><mj-spacer height="8px" /></mj-column>
      <mj-column width="49%" background-color="#F5FAFF" border="1px solid #D7E8F7" border-top="5px solid #1677B8" border-radius="16px" padding="20px 22px">
        <mj-text padding="0" font-size="12px" line-height="18px" font-weight="700" color="#075A9C" letter-spacing=".7px">APPUNTAMENTI</mj-text>
        <mj-text padding="6px 0 2px" font-size="32px" line-height="38px" font-weight="700" color="#075A9C">{appuntamenti}</mj-text>
        <mj-text padding="0" font-size="13px" line-height="19px" color="#46667E">attività da gestire</mj-text>
      </mj-column>
    </mj-section>
    <mj-section padding="8px 0"><mj-column padding="0"><mj-spacer height="1px" /></mj-column></mj-section>
    """


def genera_mjml(
    commerciale: str,
    sezioni: dict[str, list[dict]],
    oggi: date,
    *,
    logo_src: str = "../../logo%20MWR.jpg",
) -> str:
    blocchi = [
        _sezione("Opportunità scadute", "Chiudi l'opportunità se conclusa oppure aggiorna la data di chiusura prevista.", sezioni["opportunita_scadute"], tipo="opportunita"),
        _sezione("Riscontro appuntamento", "Registra l'esito, chiudi l'attività e inserisci l'eventuale opportunità commerciale.", sezioni["appuntamenti_arretrati"], tipo="appuntamento"),
        _sezione("Appuntamenti di oggi", "Dopo l'incontro ricorda di riscontrarlo nel CRM e di inserire l'eventuale opportunità commerciale.", sezioni["appuntamenti_oggi"], tipo="appuntamento"),
    ]
    corpo = "".join(blocco for blocco in blocchi if blocco)
    totale = sum(len(elementi) for elementi in sezioni.values())
    riepilogo = _riepilogo_bento(sezioni)
    return f"""<mjml>
  <mj-head>
    <mj-title>Azioni CRM da completare</mj-title>
    <mj-preview>{totale} elementi CRM da verificare - {escape(commerciale)}</mj-preview>
    <mj-attributes><mj-all font-family="Arial, Helvetica, sans-serif" /><mj-text padding="0" /></mj-attributes>
    <mj-style inline="inline">
      .opportunity-table table, .appointment-table table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
      .opportunity-table th {{ background:#FCE8EA;color:#8F101E;padding:11px 10px;text-align:left;font-weight:700; }}
      .appointment-table th {{ background:#E6F2FF;color:#075A9C;padding:11px 10px;text-align:left;font-weight:700; }}
      .opportunity-table .cell, .appointment-table .cell {{ color:#5F6368;padding:11px 10px;border-bottom:1px solid #E8EAED;vertical-align:top; }}
      .opportunity-table .client, .appointment-table .client {{ color:#202124;font-weight:700; }}
      .opportunity-table .nowrap, .appointment-table .nowrap {{ white-space:nowrap; }}
    </mj-style>
    <mj-breakpoint width="520px" />
  </mj-head>
  <mj-body background-color="#F2F4F5" width="760px">
    <mj-section background-color="#17191C" border-radius="14px 14px 0 0" padding="28px 30px 24px">
      <mj-column width="68%" vertical-align="middle">
        <mj-text font-size="12px" line-height="18px" font-weight="700" letter-spacing="1px" color="#FF9AA3" padding="0 0 8px">PERFORMANCE MANAGEMENT CRM</mj-text>
        <mj-text font-size="29px" line-height="35px" font-weight="700" color="#FFFFFF" padding="0 0 10px">Azioni CRM da completare</mj-text>
        <mj-text font-size="14px" line-height="21px" color="#CFD3D7">{oggi.strftime('%d/%m/%Y')} &nbsp;•&nbsp; {escape(commerciale)} &nbsp;•&nbsp; {totale} elementi</mj-text>
      </mj-column>
      <mj-column width="32%" vertical-align="middle">
        <mj-image src="{escape(logo_src)}" alt="My Way - Vodafone Partner" width="145px" align="right" padding="0" border-radius="8px" />
      </mj-column>
    </mj-section>
    <mj-section background-color="#FFF7DF" padding="12px 30px" border-bottom="1px solid #EADBA7">
      <mj-column><mj-text font-size="13px" line-height="19px" color="#735C0F"><strong>ANTEPRIMA LOCALE:</strong> questa e-mail non è stata inviata.</mj-text></mj-column>
    </mj-section>
    <mj-section padding="11px 0"><mj-column padding="0"><mj-spacer height="1px" /></mj-column></mj-section>
    {riepilogo}
    {corpo}
    <mj-section background-color="#17191C" border-radius="16px" padding="25px 28px">
      <mj-column width="67%" vertical-align="middle"><mj-text font-size="17px" line-height="25px" font-weight="700" color="#FFFFFF">Aggiorna direttamente i record nel CRM.<br><span style="font-size:14px;font-weight:400;color:#CFD3D7;">Questa comunicazione è un promemoria operativo e non modifica automaticamente alcun dato.</span></mj-text></mj-column>
      <mj-column width="33%" vertical-align="middle">
        <mj-button href="{CRM_TODAY_URL}" background-color="#D7192D" color="#FFFFFF" font-size="13px" font-weight="700" border-radius="20px" inner-padding="12px 20px" padding="0" align="right">APRI IL CRM</mj-button>
        <mj-text align="right" padding="9px 0 0" font-size="11px" line-height="16px" color="#CFD3D7"><a href="{CRM_TODAY_URL}" style="color:#CFD3D7;text-decoration:underline;">{CRM_TODAY_URL}</a></mj-text>
      </mj-column>
    </mj-section>
    <mj-section padding="19px 15px 24px"><mj-column><mj-text align="center" font-size="11px" color="#8A8F94">My Way S.r.l. • Controllo qualità dati CRM</mj-text></mj-column></mj-section>
  </mj-body>
</mjml>"""


def _trova_node() -> Path:
    da_path = shutil.which("node")
    if da_path:
        return Path(da_path)
    radice = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    candidati = sorted(radice.glob("OpenJS.NodeJS.LTS_*/*/node.exe"), reverse=True)
    if candidati:
        return candidati[0]
    raise RuntimeError("Node.js non trovato: installare Node.js LTS per compilare MJML")


def compila_mjml(sorgente: str) -> str:
    if not MJML_CLI.is_file():
        raise RuntimeError("Compilatore MJML non trovato: eseguire 'npm install'")
    processo = subprocess.run(
        [str(_trova_node()), str(MJML_CLI), "--stdin", "--config.validationLevel", "strict", "--noStdoutFileComment"],
        input=sorgente,
        text=True,
        capture_output=True,
        encoding="utf-8",
        cwd=PROJECT_DIR,
        check=False,
    )
    if processo.returncode != 0:
        dettaglio = processo.stderr.strip() or "errore MJML non specificato"
        raise RuntimeError(f"Compilazione MJML fallita: {dettaglio}")
    return processo.stdout


def genera_email(
    commerciale: str,
    sezioni: dict[str, list[dict]],
    oggi: date,
    *,
    logo_src: str = "../../logo%20MWR.jpg",
) -> str:
    return compila_mjml(genera_mjml(commerciale, sezioni, oggi, logo_src=logo_src))
