from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

import requests

from config import (
    SHAREPOINT_GRAPH_CLIENT_ID,
    SHAREPOINT_GRAPH_CLIENT_SECRET,
    SHAREPOINT_GRAPH_TENANT_ID,
)


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
ESTENSIONI_EXCEL = {".xlsx", ".xlsm", ".xls"}


class GraphSharePointClient:
    """Client minimale Microsoft Graph per file e cartelle SharePoint."""

    def __init__(self) -> None:
        mancanti = [
            nome
            for nome, valore in {
                "SHAREPOINT_GRAPH_CLIENT_ID": SHAREPOINT_GRAPH_CLIENT_ID,
                "SHAREPOINT_GRAPH_TENANT_ID": SHAREPOINT_GRAPH_TENANT_ID,
                "SHAREPOINT_GRAPH_CLIENT_SECRET": SHAREPOINT_GRAPH_CLIENT_SECRET,
            }.items()
            if not valore
        ]
        if mancanti:
            raise ValueError(
                "Configurazione Graph SharePoint incompleta: " + ", ".join(mancanti)
            )
        self._token: str | None = None

    def _ottieni_token(self) -> str:
        if self._token:
            return self._token
        risposta = requests.post(
            "https://login.microsoftonline.com/"
            f"{SHAREPOINT_GRAPH_TENANT_ID}/oauth2/v2.0/token",
            data={
                "client_id": SHAREPOINT_GRAPH_CLIENT_ID,
                "client_secret": SHAREPOINT_GRAPH_CLIENT_SECRET,
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=30,
        )
        risposta.raise_for_status()
        token = risposta.json().get("access_token")
        if not token:
            raise ValueError("Microsoft Graph non ha restituito un access token")
        self._token = token
        return token

    def _richiesta(
        self,
        metodo: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        contenuto: bytes | None = None,
        timeout: int = 60,
    ) -> requests.Response:
        indirizzo = url if url.startswith("https://") else f"{GRAPH_BASE_URL}{url}"
        headers_richiesta = {"Authorization": f"Bearer {self._ottieni_token()}"}
        if headers:
            headers_richiesta.update(headers)
        for tentativo in range(1, 4):
            risposta = requests.request(
                metodo,
                indirizzo,
                headers=headers_richiesta,
                params=params,
                json=json_body,
                data=contenuto,
                timeout=timeout,
            )
            if risposta.status_code not in {429, 500, 502, 503, 504}:
                risposta.raise_for_status()
                return risposta
            if tentativo == 3:
                risposta.raise_for_status()
            attesa = int(risposta.headers.get("Retry-After", tentativo * 2))
            time.sleep(min(attesa, 10))
        raise RuntimeError("Richiesta Graph non completata")

    def trova_sito(self, hostname: str, site_path: str) -> dict[str, Any]:
        percorso = quote("/" + site_path.strip("/"), safe="/")
        risposta = self._richiesta(
            "GET",
            f"/sites/{hostname}:{percorso}",
            params={"$select": "id,displayName,webUrl"},
        )
        return risposta.json()

    def trova_raccolta_documenti(
        self,
        site_id: str,
        nome_raccolta: str,
    ) -> dict[str, Any]:
        url: str | None = f"/sites/{site_id}/drives"
        raccolte: list[dict[str, Any]] = []
        while url:
            risposta = self._richiesta(
                "GET",
                url,
                params={"$select": "id,name,webUrl"} if not url.startswith("https://") else None,
            )
            dati = risposta.json()
            raccolte.extend(dati.get("value", []))
            url = dati.get("@odata.nextLink")

        cercato = nome_raccolta.casefold()
        for raccolta in raccolte:
            nome = str(raccolta.get("name", "")).casefold()
            segmento_url = unquote(urlparse(raccolta.get("webUrl", "")).path).rstrip("/")
            segmento_url = segmento_url.rsplit("/", 1)[-1].casefold()
            if cercato in {nome, segmento_url}:
                return raccolta
        disponibili = ", ".join(str(r.get("name")) for r in raccolte)
        raise FileNotFoundError(
            f"Raccolta documenti {nome_raccolta!r} non trovata. "
            f"Disponibili: {disponibili or 'nessuna'}"
        )

    def elenca_file_cartella(
        self,
        drive_id: str,
        percorso_cartella: str,
    ) -> list[dict[str, Any]]:
        percorso = quote(percorso_cartella.strip("/"), safe="/")
        url: str | None = f"/drives/{drive_id}/root:/{percorso}:/children"
        elementi: list[dict[str, Any]] = []
        while url:
            risposta = self._richiesta(
                "GET",
                url,
                params={
                    "$select": "id,name,size,eTag,lastModifiedDateTime,file,folder,parentReference",
                    "$top": "200",
                }
                if not url.startswith("https://")
                else None,
            )
            dati = risposta.json()
            elementi.extend(dati.get("value", []))
            url = dati.get("@odata.nextLink")
        return [elemento for elemento in elementi if elemento.get("file")]

    def cerca_file_avanzamenti(
        self,
        drive_id: str,
        percorso_cartella: str,
    ) -> list[dict[str, Any]]:
        file_trovati = [
            elemento
            for elemento in self.elenca_file_cartella(drive_id, percorso_cartella)
            if "avanzamenti" in str(elemento.get("name", "")).casefold()
            and Path(str(elemento.get("name", ""))).suffix.casefold()
            in ESTENSIONI_EXCEL
            and not str(elemento.get("name", "")).startswith("~$")
        ]
        return sorted(
            file_trovati,
            key=lambda elemento: str(elemento.get("lastModifiedDateTime", "")),
            reverse=True,
        )

    def scarica_file(self, drive_id: str, item_id: str) -> bytes:
        risposta = self._richiesta(
            "GET",
            f"/drives/{drive_id}/items/{quote(item_id, safe='')}/content",
            timeout=120,
        )
        return risposta.content

    def elimina_file(self, drive_id: str, item_id: str, etag: str) -> None:
        """Sposta nel cestino un file solo se non è cambiato dal download."""
        if not etag:
            raise ValueError(f"eTag mancante per l'elemento Graph {item_id}")
        self._richiesta(
            "DELETE",
            f"/drives/{drive_id}/items/{quote(item_id, safe='')}",
            headers={"If-Match": etag},
        )

    def _elenca_figli(self, drive_id: str, item_id: str) -> list[dict[str, Any]]:
        url: str | None = f"/drives/{drive_id}/items/{quote(item_id, safe='')}/children"
        elementi: list[dict[str, Any]] = []
        while url:
            risposta = self._richiesta(
                "GET",
                url,
                params={"$select": "id,name,folder,file,webUrl", "$top": "200"}
                if not url.startswith("https://")
                else None,
            )
            dati = risposta.json()
            elementi.extend(dati.get("value", []))
            url = dati.get("@odata.nextLink")
        return elementi

    def crea_percorso_cartelle(
        self,
        drive_id: str,
        percorso_cartelle: str,
    ) -> dict[str, Any]:
        """Trova o crea, segmento per segmento, un percorso nel drive."""
        radice = self._richiesta(
            "GET",
            f"/drives/{drive_id}/root",
            params={"$select": "id,name,folder,webUrl"},
        ).json()
        cartella_corrente = radice

        for segmento in [p.strip() for p in percorso_cartelle.split("/") if p.strip()]:
            figli = self._elenca_figli(drive_id, cartella_corrente["id"])
            corrispondenze = [
                elemento
                for elemento in figli
                if elemento.get("folder") is not None
                and str(elemento.get("name", "")).casefold() == segmento.casefold()
            ]
            if len(corrispondenze) > 1:
                raise ValueError(
                    f"Più cartelle chiamate {segmento!r} sotto "
                    f"{cartella_corrente.get('name')!r}"
                )
            if corrispondenze:
                cartella_corrente = corrispondenze[0]
                continue

            cartella_corrente = self._richiesta(
                "POST",
                f"/drives/{drive_id}/items/"
                f"{quote(cartella_corrente['id'], safe='')}/children",
                headers={"Content-Type": "application/json"},
                json_body={
                    "name": segmento,
                    "folder": {},
                    "@microsoft.graph.conflictBehavior": "fail",
                },
            ).json()
            print(f"  ✓ Cartella SharePoint creata: {segmento}")

        return cartella_corrente

    def carica_file(
        self,
        drive_id: str,
        cartella_id: str,
        file_locale: Path,
    ) -> dict[str, Any]:
        """Carica o sostituisce un file fino a 250 MB nella cartella indicata."""
        file_locale = Path(file_locale)
        if not file_locale.is_file():
            raise FileNotFoundError(f"File da caricare non trovato: {file_locale}")
        if file_locale.stat().st_size > 250 * 1024 * 1024:
            raise ValueError("Il file supera 250 MB: è necessaria una upload session")
        nome_file = quote(file_locale.name, safe="")
        risposta = self._richiesta(
            "PUT",
            f"/drives/{drive_id}/items/{quote(cartella_id, safe='')}:"
            f"/{nome_file}:/content",
            headers={
                "Content-Type": (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            },
            contenuto=file_locale.read_bytes(),
            timeout=180,
        )
        return risposta.json()
