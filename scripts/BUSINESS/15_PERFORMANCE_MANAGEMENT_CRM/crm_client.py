from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests

from config import API_KEY, BASE_URL, TIMEZONE


UTC = ZoneInfo("UTC")
ROME = ZoneInfo(TIMEZONE)

STATO_OPPORTUNITA = {59096: "Aperta", 59101: "Persa", 59100: "Acquisita"}
STATO_ATTIVITA = {0: "Attività da fare", 1: "Annullata", 2: "Attività fatta"}
TIPO_APPUNTAMENTO = {"1": "CB", "2": "Autoprocurato CB", "3": "Prospect"}


def data_locale(valore: Any) -> datetime | None:
    if not valore:
        return None
    testo = str(valore).strip()
    try:
        istante = datetime.fromisoformat(testo.replace("Z", "+00:00"))
        if istante.tzinfo is None:
            istante = istante.replace(tzinfo=UTC)
        return istante.astimezone(ROME)
    except (TypeError, ValueError):
        return None


class CrmClient:
    def __init__(self, *, timeout: int = 30, tentativi: int = 5) -> None:
        self.timeout = timeout
        self.tentativi = tentativi
        self.session = requests.Session()
        self.anomalie_anagrafiche: list[dict[str, str]] = []

    def get_json(self, endpoint: str, params: dict | None = None) -> Any:
        query = dict(params or {})
        query["apikey"] = API_KEY
        ultimo_errore: Exception | None = None
        for tentativo in range(1, self.tentativi + 1):
            try:
                risposta = self.session.get(
                    f"{BASE_URL}/{endpoint}",
                    params=query,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
                risposta.raise_for_status()
                return risposta.json()
            except (requests.RequestException, ValueError) as errore:
                ultimo_errore = errore
                if tentativo < self.tentativi:
                    time.sleep(min(2 * tentativo, 10))
        # Le eccezioni di requests possono includere l'URL completo e quindi
        # anche la chiave API presente nella query string. Non propagarle mai.
        tipo_errore = type(ultimo_errore).__name__ if ultimo_errore else "Errore sconosciuto"
        raise RuntimeError(f"Lettura CRM fallita per {endpoint} ({tipo_errore})")

    def scarica_tutto(self, endpoint: str, *, top: int = 10) -> list[dict]:
        risultati: list[dict] = []
        offset = 0
        while True:
            batch = self.get_json(endpoint, {"top": top, "skip": offset})
            if not isinstance(batch, list):
                raise RuntimeError(f"Risposta inattesa da {endpoint}: attesa una lista")
            if not batch:
                return risultati
            risultati.extend(batch)
            print(f"  {endpoint}: {len(risultati)} record", end="\r", flush=True)
            if len(batch) < top:
                print()
                return risultati
            offset += top

    def _prefetch(
        self,
        ids: set[Any],
        funzione: Callable[[Any], tuple[Any, Any]],
        etichetta: str,
        *,
        obbligatorio: bool = True,
    ) -> dict[Any, Any]:
        risultati: dict[Any, Any] = {}
        errori: list[str] = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_per_id = {executor.submit(funzione, item_id): item_id for item_id in ids}
            for future in as_completed(future_per_id):
                item_id = future_per_id[future]
                try:
                    chiave, valore = future.result()
                    risultati[chiave] = valore
                except Exception as errore:  # il dettaglio confluisce nell'errore complessivo
                    errori.append(f"{item_id}: {errore}")
        if errori and obbligatorio:
            esempio = "; ".join(errori[:3])
            raise RuntimeError(
                f"Arricchimento {etichetta} incompleto: {len(errori)} errori. {esempio}"
            )
        for errore in errori:
            self.anomalie_anagrafiche.append({"tipo": etichetta, "dettaglio": errore})
        return risultati

    def estrai_opportunita(self) -> list[dict]:
        print("Estrazione opportunità...")
        opportunita = self.scarica_tutto("Opportunity/Search")
        company_ids = {item.get("crossId") for item in opportunita if item.get("crossId")}
        user_ids = {
            user_id
            for item in opportunita
            for user_id in (item.get("salesPersons") or [])[:1]
            if user_id
        }

        aziende = self._prefetch(
            company_ids,
            lambda item_id: (item_id, self.get_json(f"Company/{item_id}").get("companyName")),
            "aziende opportunità",
            obbligatorio=False,
        )
        utenti = self._prefetch(user_ids, self._leggi_utente, "proprietari opportunità")

        righe = []
        for item in opportunita:
            proprietari = item.get("salesPersons") or []
            prodotti = []
            for prodotto in item.get("products") or []:
                nome_prodotto = str(prodotto.get("productName") or "").strip()
                if nome_prodotto and nome_prodotto not in prodotti:
                    prodotti.append(nome_prodotto)
            righe.append(
                {
                    "id": item.get("id"),
                    "company_id": item.get("crossId"),
                    "codice": f"TO400000{item.get('code')}",
                    "cliente": aziende.get(item.get("crossId")),
                    "prodotto": ", ".join(prodotti) or None,
                    "proprietario": utenti.get(proprietari[0]) if proprietari else None,
                    "stato": STATO_OPPORTUNITA.get(item.get("phase"), str(item.get("phase"))),
                    "data_creazione": data_locale(item.get("createdDate")),
                    "data_chiusura": data_locale(item.get("closeDate")),
                }
            )
        return righe

    def estrai_appuntamenti(self) -> list[dict]:
        print("Estrazione appuntamenti...")
        attivita = self.scarica_tutto("Activity/Search")
        appuntamenti = [item for item in attivita if item.get("type") == 6]
        company_ids = {item.get("companyId") for item in appuntamenti if item.get("companyId")}
        lead_ids = {item.get("leadId") for item in appuntamenti if item.get("leadId")}
        user_ids = {item.get("ownerId") for item in appuntamenti if item.get("ownerId")}

        aziende = self._prefetch(
            company_ids,
            lambda item_id: (item_id, self.get_json(f"Company/{item_id}").get("companyName")),
            "aziende appuntamenti",
            obbligatorio=False,
        )
        lead = self._prefetch(
            lead_ids, self._leggi_lead, "lead appuntamenti", obbligatorio=False
        )
        utenti = self._prefetch(user_ids, self._leggi_utente, "proprietari appuntamenti")

        righe = []
        for item in appuntamenti:
            cliente = aziende.get(item.get("companyId")) or lead.get(item.get("leadId"))
            righe.append(
                {
                    "id": item.get("id"),
                    "company_id": item.get("companyId"),
                    "lead_id": item.get("leadId"),
                    "cliente": cliente,
                    "proprietario": utenti.get(item.get("ownerId")),
                    "stato": STATO_ATTIVITA.get(item.get("state"), str(item.get("state"))),
                    "data": data_locale(item.get("activityDate")),
                    "tipo": TIPO_APPUNTAMENTO.get(
                        str(item.get("FF_VIC_TIPOAPP")) if item.get("FF_VIC_TIPOAPP") is not None else None,
                        "Non indicato",
                    ),
                }
            )
        return righe

    def _leggi_utente(self, user_id: Any) -> tuple[Any, str | None]:
        account = self.get_json("Account/Get", {"id": user_id})
        alias = account.get("aliases") or []
        return user_id, alias[0] if alias else None

    def _leggi_lead(self, lead_id: Any) -> tuple[Any, str | None]:
        lead = self.get_json(f"Lead/{lead_id}")
        for chiave in ("companyName", "name", "fullName", "firstName"):
            if lead.get(chiave):
                return lead_id, str(lead[chiave])
        return lead_id, None

