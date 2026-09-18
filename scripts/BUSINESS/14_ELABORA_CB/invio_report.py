import os
import re
import base64
from datetime import datetime
from html import escape, unescape
from pathlib import Path
from urllib.parse import quote

import requests

from config import (
    EMAIL_DRY_RUN,
    GOVERNANCE_EMAIL,
    GRAPH_CLIENT_ID,
    GRAPH_CLIENT_SECRET,
    GRAPH_SENDER_EMAIL,
    GRAPH_TENANT_ID,
)
from console import avviso, errore, info, successo


# Conserva il percorso del report durante la simulazione. Outlook non espone
# sempre il percorso completo dell'allegato finché il messaggio non è salvato.
_FILE_REPORT_CORRENTE: Path | None = None
_DATA_ESECUZIONE_CORRENTE: datetime | None = None


class _AllegatoSimulato:
    """Rappresentazione minima di un allegato quando Outlook non è disponibile."""

    def __init__(self, percorso: str):
        self.PathName = percorso
        self.FileName = Path(percorso).name


class _AllegatiSimulati:
    """Collezione compatibile con i metodi COM Add, Count e Item."""

    def __init__(self):
        self._elementi = []

    @property
    def Count(self) -> int:
        return len(self._elementi)

    def Add(self, percorso: str):
        allegato = _AllegatoSimulato(percorso)
        self._elementi.append(allegato)
        return allegato

    def Item(self, indice: int):
        # Le collezioni COM di Outlook usano indici che partono da 1.
        return self._elementi[indice - 1]


class _MailSimulata:
    """Oggetto mail locale usato nel dry-run se Outlook non è disponibile."""

    def __init__(self):
        self.To = ""
        self.CC = ""
        self.BCC = ""
        self.Subject = ""
        self.HTMLBody = ""
        self.Attachments = _AllegatiSimulati()


def _dry_run_attivo(valore) -> bool:
    """Accetta sia un booleano sia la stringa 'true'."""

    if isinstance(valore, bool):
        return valore

    return str(valore).strip().lower() == "true"


def _descrizione_destinatari(indirizzi: str) -> str:
    """Descrive chiaramente se il valore email è singolo o multiplo."""

    valore = str(indirizzi or "").strip()

    if not valore:
        return "stringa vuota (nessun destinatario configurato)"

    elementi = [
        indirizzo.strip()
        for indirizzo in valore.split(";")
        if indirizzo.strip()
    ]

    if len(elementi) > 1:
        return (
            f"stringa multipla: {len(elementi)} destinatari "
            "separati da punto e virgola"
        )

    return "stringa singola: 1 destinatario"


def _stampa_header(file_html: Path, dry_run: bool) -> None:
    """Stampa i dati di configurazione letti da SCRIPT/.env."""

    data_esecuzione = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    print("\n" + "=" * 72)
    print("INVIO REPORT GOVERNANCE")
    print("=" * 72)
    print(f"Data/ora esecuzione : {data_esecuzione}")
    print(f"EMAIL_DRY_RUN       : {dry_run}")
    print(f"GOVERNANCE_EMAIL    : {GOVERNANCE_EMAIL!r}")
    print(
        "Tipo destinatario   : "
        f"{_descrizione_destinatari(GOVERNANCE_EMAIL)}"
    )
    print(f"File report HTML    : {file_html.resolve()}")
    print("=" * 72)


def _apri_nel_browser(file_html: Path) -> None:
    """Apre il report nel browser quando l'invio reale non è disponibile."""

    try:
        os.startfile(str(file_html))
    except OSError as eccezione:
        errore(f"Impossibile aprire il report nel browser: {eccezione}")


def _corpo_email(analisi: dict, data_ora: str) -> str:
    """Costruisce il corpo HTML con il riepilogo dell'analisi."""

    righe_riepilogo = "".join(
        "<li>"
        f"<strong>{escape(stato.replace('_', ' ').title())}</strong>: "
        f"{totale}"
        "</li>"
        for stato, totale in sorted(
            analisi.get("riepilogo", {}).items()
        )
    )
    totale_aziende = len(analisi.get("risultati", []))

    return (
        "<html><body>"
        "<p>Buongiorno,</p>"
        f"<p>in allegato il report dell'analisi CB del {data_ora}.</p>"
        f"<p><strong>Aziende analizzate:</strong> {totale_aziende}</p>"
        f"<ul>{righe_riepilogo}</ul>"
        "<p>Il dettaglio completo è disponibile nel report HTML allegato.</p>"
        "<p>Cordiali saluti</p>"
        "</body></html>"
    )


def _testo_da_html(corpo_html: str) -> str:
    """Produce un'anteprima testuale semplice del corpo HTML."""

    testo = re.sub(r"<[^>]+>", " ", corpo_html)
    testo = unescape(testo)
    return " ".join(testo.split())


def _percorsi_allegati(mail) -> list[str]:
    """Estrae i percorsi dagli allegati Outlook o dalla mail simulata."""

    percorsi = []
    try:
        allegati = mail.Attachments
        totale = int(allegati.Count)
    except Exception:
        return percorsi

    for indice in range(1, totale + 1):
        try:
            allegato = allegati.Item(indice)
            percorso = str(
                getattr(allegato, "PathName", "") or ""
            ).strip()
        except Exception:
            percorso = ""

        # Per il report allegato possiamo sempre mostrare il percorso noto.
        if not percorso and indice == 1 and _FILE_REPORT_CORRENTE:
            percorso = str(_FILE_REPORT_CORRENTE.resolve())

        if not percorso:
            try:
                percorso = str(
                    getattr(
                        allegato,
                        "FileName",
                        "Percorso non disponibile",
                    )
                )
            except Exception:
                percorso = "Percorso non disponibile"

        percorsi.append(percorso)

    return percorsi


def _valore_mail(mail, attributo: str, predefinito=""):
    """Legge una proprietà COM senza interrompere il logging in caso di errore."""

    try:
        return getattr(mail, attributo, predefinito)
    except Exception:
        return predefinito


def _lista_destinatari(*campi) -> list[str]:
    """Converte i campi Outlook separati da ';' in una lista pulita."""

    destinatari = []

    for campo in campi:
        destinatari.extend(
            indirizzo.strip()
            for indirizzo in str(campo or "").split(";")
            if indirizzo.strip()
        )

    return destinatari


def _dimensione_file(percorso: Path) -> str:
    """Restituisce la dimensione del file in KB o MB."""

    try:
        dimensione = percorso.stat().st_size
    except OSError:
        return "non disponibile"

    dimensione_kb = dimensione / 1024

    if dimensione_kb >= 1024:
        return f"{dimensione_kb / 1024:.1f} MB"

    return f"{dimensione_kb:.1f} KB"


def scrivi_log_email(
    mail,
    esito,
    dettaglio_errore=None,
    message_id=None,
):
    """Scrive su disco tutti i dettagli dell'invio o della simulazione."""

    try:
        data_esito = datetime.now()
        data_esecuzione = _DATA_ESECUZIONE_CORRENTE or data_esito
        dry_run = _dry_run_attivo(EMAIL_DRY_RUN)
        stato = str(esito).strip().upper()

        # Il log viene salvato nella cartella LOG accanto al report HTML.
        if _FILE_REPORT_CORRENTE is None:
            raise ValueError("Percorso del report non disponibile")

        cartella_log = _FILE_REPORT_CORRENTE.resolve().parent / "LOG"
        cartella_log.mkdir(parents=True, exist_ok=True)
        nome_file = data_esito.strftime("EMAIL_LOG_%Y%m%d_%H%M%S.txt")
        file_log = cartella_log / nome_file

        destinatario_to = str(_valore_mail(mail, "To") or "").strip()
        destinatari_cc = str(_valore_mail(mail, "CC") or "").strip()
        destinatari_bcc = str(_valore_mail(mail, "BCC") or "").strip()
        elenco_destinatari = _lista_destinatari(
            destinatario_to,
            destinatari_cc,
            destinatari_bcc,
        )
        corpo_html = str(_valore_mail(mail, "HTMLBody") or "")
        corpo_testo = _testo_da_html(corpo_html)
        formato_corpo = (
            "HTML"
            if re.search(r"<[^>]+>", corpo_html)
            else "TESTO"
        )
        oggetto = str(_valore_mail(mail, "Subject") or "")

        # Il report viene sempre riportato per primo nell'elenco allegati.
        percorso_report = _FILE_REPORT_CORRENTE.resolve()
        percorsi_allegati = [
            Path(percorso).resolve()
            for percorso in _percorsi_allegati(mail)
            if percorso
        ]
        percorsi_ordinati = [percorso_report]

        for percorso in percorsi_allegati:
            if percorso != percorso_report:
                percorsi_ordinati.append(percorso)

        righe_allegati = []
        for indice, percorso in enumerate(percorsi_ordinati, start=1):
            righe_allegati.append(
                f"Allegato {indice} : {percorso.name} | "
                f"{percorso} (dimensione: {_dimensione_file(percorso)})"
            )

        dettaglio = (
            str(dettaglio_errore)
            if dettaglio_errore
            else "(nessuno)"
        )
        id_messaggio = (
            str(message_id)
            if message_id
            else "N/A"
        )
        to_visualizzato = destinatario_to or "(nessuno)"
        cc_visualizzato = destinatari_cc or "(nessuno)"
        bcc_visualizzato = destinatari_bcc or "(nessuno)"
        elenco_visualizzato = (
            "\n".join(
                f"  - {indirizzo}"
                for indirizzo in elenco_destinatari
            )
            if elenco_destinatari
            else "  - (nessuno)"
        )

        contenuto = (
            f"{'=' * 67}\n"
            f"EMAIL LOG - {data_esito:%Y-%m-%d %H:%M:%S}\n"
            f"{'=' * 67}\n\n"
            "[1] CONFIGURAZIONE\n\n"
            f"Data/ora esecuzione : {data_esecuzione:%Y-%m-%d %H:%M:%S}\n"
            f"EMAIL_DRY_RUN : {str(dry_run).lower()}\n"
            f"GOVERNANCE_EMAIL : {GOVERNANCE_EMAIL}\n\n"
            "[2] DESTINATARI\n\n"
            f"A (TO) : {to_visualizzato}\n"
            f"CC : {cc_visualizzato}\n"
            f"BCC : {bcc_visualizzato}\n"
            f"Numero destinatari : {len(elenco_destinatari)}\n"
            f"Elenco completo :\n{elenco_visualizzato}\n\n"
            "[3] OGGETTO\n\n"
            f"{oggetto}\n\n"
            "[4] CORPO EMAIL\n\n"
            f"Formato : {formato_corpo}\n"
            f"Anteprima (testo) : {corpo_testo[:500]}\n"
            f"Lunghezza (caratteri) : {len(corpo_html)}\n\n"
            "[5] ALLEGATI\n\n"
            f"Numero allegati : {len(percorsi_ordinati)}\n"
            f"{chr(10).join(righe_allegati)}\n\n"
            "[6] ESITO INVIO\n\n"
            f"Stato : {stato}\n"
            f"Timestamp invio : {data_esito:%Y-%m-%d %H:%M:%S}\n"
            f"Dettaglio errore : {dettaglio}\n"
            f"ID messaggio Graph/Outlook : {id_messaggio}\n\n"
            f"{'=' * 67}\n"
        )

        file_log.write_text(contenuto, encoding="utf-8")
        info(f"Log email salvato: {file_log}")
        return file_log
    except Exception as eccezione:
        # Un problema nel log non deve interrompere il processo principale.
        avviso(f"Impossibile scrivere il log email: {eccezione}")
        return None


def simula_invio(mail) -> None:
    """Stampa tutti i dati della mail senza chiamare mail.Send()."""

    corpo_html = str(getattr(mail, "HTMLBody", "") or "")
    corpo_testo = _testo_da_html(corpo_html)
    contiene_html = bool(re.search(r"<[^>]+>", corpo_html))
    data_simulazione = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    destinatario_mail = str(getattr(mail, "To", "") or "").strip()
    destinatario_effettivo = destinatario_mail or GOVERNANCE_EMAIL

    print("\n" + "-" * 72)
    print("SIMULAZIONE INVIO EMAIL - NESSUNA EMAIL VERRÀ INVIATA")
    print("-" * 72)
    print(f"Data/ora simulazione : {data_simulazione}")
    print(
        "DESTINATARIO EMAIL   : "
        f"{destinatario_effettivo or 'Nessuno'}"
    )
    print(
        "Destinatario da SCRIPT/.env : "
        f"{GOVERNANCE_EMAIL or 'Non configurato'}"
    )
    print(f"Valore Outlook mail.To: {destinatario_mail or 'Vuoto'}")
    print(f"Destinatari CC       : {getattr(mail, 'CC', '') or 'Nessuno'}")
    print(f"Destinatari BCC      : {getattr(mail, 'BCC', '') or 'Nessuno'}")
    destinatari_completi = _lista_destinatari(
        destinatario_effettivo,
        getattr(mail, "CC", ""),
        getattr(mail, "BCC", ""),
    )
    print("Elenco completo destinatari:")
    if destinatari_completi:
        for indice, indirizzo in enumerate(
            destinatari_completi,
            start=1,
        ):
            print(f"  {indice}. {indirizzo}")
    else:
        print("  (nessuno)")
    print(f"Oggetto              : {getattr(mail, 'Subject', '')}")
    print(f"Corpo in formato HTML: {'Sì' if contiene_html else 'No'}")
    print(f"Corpo HTML (primi 200 caratteri): {corpo_html[:200]}")

    if contiene_html:
        print(
            "Testo piano (primi 200 caratteri): "
            f"{corpo_testo[:200]}"
        )

    percorsi_allegati = _percorsi_allegati(mail)
    print(f"Numero allegati      : {len(percorsi_allegati)}")

    for indice, percorso in enumerate(percorsi_allegati, start=1):
        print(f"Allegato {indice:<12}: {percorso}")

    percorso_report = (
        str(_FILE_REPORT_CORRENTE.resolve())
        if _FILE_REPORT_CORRENTE
        else "Non disponibile"
    )
    print(f"File report HTML     : {percorso_report}")
    print("-" * 72)


def _configura_mail(mail, file_html: Path, analisi: dict) -> None:
    """Imposta destinatari, oggetto, corpo e allegato."""

    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
    mail.To = GOVERNANCE_EMAIL
    mail.CC = ""
    mail.BCC = ""
    mail.Subject = f"Report Analisi CB - {data_ora}"
    mail.HTMLBody = _corpo_email(analisi, data_ora)
    mail.Attachments.Add(str(file_html.resolve()))

    # Questa stampa non dipende dalla risoluzione dei destinatari di Outlook.
    print(f"Destinatario configurato: {GOVERNANCE_EMAIL}")


def _configurazione_graph_mancante() -> list[str]:
    configurazione = {
        "GRAPH_CLIENT_ID": GRAPH_CLIENT_ID,
        "GRAPH_TENANT_ID": GRAPH_TENANT_ID,
        "GRAPH_CLIENT_SECRET": GRAPH_CLIENT_SECRET,
        "GRAPH_SENDER_EMAIL": GRAPH_SENDER_EMAIL,
    }
    return [nome for nome, valore in configurazione.items() if not valore]


def _token_graph() -> str:
    url = (
        "https://login.microsoftonline.com/"
        f"{GRAPH_TENANT_ID}/oauth2/v2.0/token"
    )
    risposta = requests.post(
        url,
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


def _destinatari_graph() -> list[dict]:
    return [
        {"emailAddress": {"address": indirizzo}}
        for indirizzo in _lista_destinatari(GOVERNANCE_EMAIL)
    ]


def _invia_con_graph(file_html: Path, analisi: dict) -> None:
    """Invia il report con Microsoft Graph in modalita' app-only."""

    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
    contenuto_allegato = base64.b64encode(
        file_html.read_bytes()
    ).decode("ascii")
    payload = {
        "message": {
            "subject": f"Report Analisi CB - {data_ora}",
            "body": {
                "contentType": "HTML",
                "content": _corpo_email(analisi, data_ora),
            },
            "toRecipients": _destinatari_graph(),
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": file_html.name,
                    "contentType": "text/html",
                    "contentBytes": contenuto_allegato,
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


def invia_report(file_html: Path, analisi: dict) -> bool:
    """Simula o invia il report in base a EMAIL_DRY_RUN."""

    global _DATA_ESECUZIONE_CORRENTE, _FILE_REPORT_CORRENTE

    file_html = Path(file_html)
    dry_run = _dry_run_attivo(EMAIL_DRY_RUN)
    _FILE_REPORT_CORRENTE = file_html
    _DATA_ESECUZIONE_CORRENTE = datetime.now()

    if dry_run:
        print("EMAIL: modalità SIMULAZIONE, nessun messaggio sarà inviato.")
    else:
        print("EMAIL: modalità INVIO REALE.")

    # L'header conferma i valori caricati da SCRIPT/.env prima di ogni controllo.
    _stampa_header(file_html, dry_run)

    if not GOVERNANCE_EMAIL:
        mail = _MailSimulata()
        _configura_mail(mail, file_html, analisi)
        scrivi_log_email(
            mail,
            "FALLITO",
            "Indirizzo email Governance non configurato",
        )
        avviso(
            "Indirizzo email Governance non configurato. Invio saltato."
        )
        return False

    if not file_html.exists():
        mail = _MailSimulata()
        _configura_mail(mail, file_html, analisi)
        scrivi_log_email(
            mail,
            "FALLITO",
            "File report non trovato",
        )
        errore("File report non trovato")
        return False

    mail = _MailSimulata()
    _configura_mail(mail, file_html, analisi)

    if dry_run:
        simula_invio(mail)
        scrivi_log_email(mail, "SIMULATO")
        info("Dry-run completato: nessuna email inviata.")
        return False

    mancanti = _configurazione_graph_mancante()
    if mancanti:
        dettaglio_errore = (
            "Configurazione Microsoft Graph mancante: "
            + ", ".join(mancanti)
        )
        scrivi_log_email(mail, "FALLITO", dettaglio_errore)
        errore(dettaglio_errore)
        return False

    try:
        info(f"Invio report Graph da {GRAPH_SENDER_EMAIL} a {GOVERNANCE_EMAIL}")
        _invia_con_graph(file_html, analisi)
        scrivi_log_email(mail, "INVIATO")
        successo("Report inviato al team Governance tramite Microsoft Graph.")
        return True
    except requests.RequestException as eccezione:
        dettaglio = str(eccezione)
        risposta = getattr(eccezione, "response", None)
        if risposta is not None and risposta.text:
            dettaglio = f"{dettaglio} - {risposta.text}"
        scrivi_log_email(mail, "FALLITO", dettaglio)
        errore(f"Invio Microsoft Graph fallito: {dettaglio}")
        return False
    except Exception as eccezione:
        scrivi_log_email(mail, "FALLITO", str(eccezione))
        errore(f"Invio Microsoft Graph fallito: {eccezione}")
        return False
