"""Operazioni SharePoint riutilizzabili tramite Microsoft Graph."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

import requests

import config_env  # noqa: F401


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class GraphSharePointClient:
    def __init__(self) -> None:
        self.client_id = os.getenv("SHAREPOINT_GRAPH_CLIENT_ID", "").strip()
        self.tenant_id = os.getenv("SHAREPOINT_GRAPH_TENANT_ID", "").strip()
        self.client_secret = os.getenv(
            "SHAREPOINT_GRAPH_CLIENT_SECRET", ""
        ).strip()
        mancanti = [
            nome
            for nome, valore in {
                "SHAREPOINT_GRAPH_CLIENT_ID": self.client_id,
                "SHAREPOINT_GRAPH_TENANT_ID": self.tenant_id,
                "SHAREPOINT_GRAPH_CLIENT_SECRET": self.client_secret,
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
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=30,
        )
        risposta.raise_for_status()
        self._token = risposta.json().get("access_token")
        if not self._token:
            raise ValueError("Microsoft Graph non ha restituito un access token")
        return self._token

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
        intestazioni = {"Authorization": f"Bearer {self._ottieni_token()}"}
        if headers:
            intestazioni.update(headers)
        for tentativo in range(1, 4):
            risposta = requests.request(
                metodo,
                indirizzo,
                headers=intestazioni,
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
        return self._richiesta(
            "GET",
            f"/sites/{hostname}:{percorso}",
            params={"$select": "id,displayName,webUrl"},
        ).json()

    def trova_raccolta_documenti(
        self, site_id: str, nome_raccolta: str
    ) -> dict[str, Any]:
        url: str | None = f"/sites/{site_id}/drives"
        raccolte: list[dict[str, Any]] = []
        while url:
            risposta = self._richiesta(
                "GET",
                url,
                params={"$select": "id,name,webUrl"} if not url.startswith("https://") else None,
            ).json()
            raccolte.extend(risposta.get("value", []))
            url = risposta.get("@odata.nextLink")
        cercato = nome_raccolta.casefold()
        for raccolta in raccolte:
            nome = str(raccolta.get("name", "")).casefold()
            segmento = unquote(urlparse(raccolta.get("webUrl", "")).path).rstrip("/")
            segmento = segmento.rsplit("/", 1)[-1].casefold()
            if cercato in {nome, segmento}:
                return raccolta
        disponibili = ", ".join(str(item.get("name")) for item in raccolte)
        raise FileNotFoundError(
            f"Raccolta {nome_raccolta!r} non trovata. Disponibili: {disponibili}"
        )

    def _elenca_figli(self, drive_id: str, item_id: str) -> list[dict[str, Any]]:
        url: str | None = f"/drives/{drive_id}/items/{quote(item_id, safe='')}/children"
        elementi: list[dict[str, Any]] = []
        while url:
            risposta = self._richiesta(
                "GET",
                url,
                params={
                    "$select": "id,name,size,eTag,lastModifiedDateTime,file,folder,webUrl,parentReference",
                    "$top": "200",
                }
                if not url.startswith("https://")
                else None,
            ).json()
            elementi.extend(risposta.get("value", []))
            url = risposta.get("@odata.nextLink")
        return elementi

    def crea_percorso_cartelle(
        self, drive_id: str, percorso_cartelle: str
    ) -> dict[str, Any]:
        corrente = self._richiesta(
            "GET", f"/drives/{drive_id}/root", params={"$select": "id,name,folder,webUrl"}
        ).json()
        for segmento in [p.strip() for p in percorso_cartelle.split("/") if p.strip()]:
            figli = self._elenca_figli(drive_id, corrente["id"])
            trovate = [
                elemento
                for elemento in figli
                if elemento.get("folder") is not None
                and str(elemento.get("name", "")).casefold() == segmento.casefold()
            ]
            if len(trovate) > 1:
                raise ValueError(f"Più cartelle chiamate {segmento!r}")
            if trovate:
                corrente = trovate[0]
            else:
                corrente = self._richiesta(
                    "POST",
                    f"/drives/{drive_id}/items/{quote(corrente['id'], safe='')}/children",
                    headers={"Content-Type": "application/json"},
                    json_body={
                        "name": segmento,
                        "folder": {},
                        "@microsoft.graph.conflictBehavior": "fail",
                    },
                ).json()
                print(f"  OK Cartella SharePoint creata: {segmento}")
        return corrente

    def elenca_file_cartella(
        self, drive_id: str, percorso_cartella: str, *, crea: bool = False
    ) -> list[dict[str, Any]]:
        if crea:
            cartella = self.crea_percorso_cartelle(drive_id, percorso_cartella)
            elementi = self._elenca_figli(drive_id, cartella["id"])
        else:
            percorso = quote(percorso_cartella.strip("/"), safe="/")
            risposta = self._richiesta(
                "GET",
                f"/drives/{drive_id}/root:/{percorso}:/children",
                params={
                    "$select": "id,name,size,eTag,lastModifiedDateTime,file,folder,webUrl,parentReference",
                    "$top": "200",
                },
            ).json()
            elementi = risposta.get("value", [])
        return [elemento for elemento in elementi if elemento.get("file")]

    def scarica_file(self, drive_id: str, item_id: str) -> bytes:
        return self._richiesta(
            "GET",
            f"/drives/{drive_id}/items/{quote(item_id, safe='')}/content",
            timeout=180,
        ).content

    def elimina_file(self, drive_id: str, item_id: str, etag: str) -> None:
        """Elimina un elemento solo se non e' cambiato rispetto all'eTag letto."""
        if not etag:
            raise ValueError(f"eTag mancante per l'elemento Graph {item_id}")
        self._richiesta(
            "DELETE",
            f"/drives/{drive_id}/items/{quote(item_id, safe='')}",
            headers={"If-Match": etag},
        )

    def cerca_file(self, drive_id: str, testo: str) -> list[dict[str, Any]]:
        """Cerca file per nome nell'intera raccolta documenti."""
        url: str | None = (
            f"/drives/{drive_id}/root/search(q='{quote(testo, safe='')}')"
        )
        elementi: list[dict[str, Any]] = []
        while url:
            risposta = self._richiesta(
                "GET",
                url,
                params={
                    "$select": (
                        "id,name,size,eTag,lastModifiedDateTime,file,webUrl,"
                        "parentReference"
                    )
                }
                if not url.startswith("https://")
                else None,
            ).json()
            elementi.extend(risposta.get("value", []))
            url = risposta.get("@odata.nextLink")
        return [elemento for elemento in elementi if elemento.get("file")]

    def sposta_elemento(
        self,
        drive_id: str,
        item_id: str,
        cartella_destinazione_id: str,
    ) -> dict[str, Any]:
        """Sposta un file o una cartella nello stesso drive SharePoint."""
        return self._richiesta(
            "PATCH",
            f"/drives/{drive_id}/items/{quote(item_id, safe='')}",
            headers={"Content-Type": "application/json"},
            json_body={
                "parentReference": {"id": cartella_destinazione_id},
            },
            timeout=180,
        ).json()

    def carica_bytes(
        self,
        drive_id: str,
        percorso_cartella: str,
        nome_file: str,
        contenuto: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        if len(contenuto) > 250 * 1024 * 1024:
            raise ValueError("Il file supera 250 MB: serve una upload session")
        cartella = self.crea_percorso_cartelle(drive_id, percorso_cartella)
        return self._richiesta(
            "PUT",
            f"/drives/{drive_id}/items/{quote(cartella['id'], safe='')}:"
            f"/{quote(nome_file, safe='')}:/content",
            headers={"Content-Type": content_type},
            contenuto=contenuto,
            timeout=180,
        ).json()

    def carica_file(
        self,
        drive_id: str,
        cartella_id: str,
        file_locale: Path,
    ) -> dict[str, Any]:
        """Carica o sostituisce un file locale in una cartella Graph gia' risolta."""
        file_locale = Path(file_locale)
        if not file_locale.is_file():
            raise FileNotFoundError(f"File da caricare non trovato: {file_locale}")
        contenuto = file_locale.read_bytes()
        if len(contenuto) > 250 * 1024 * 1024:
            raise ValueError("Il file supera 250 MB: serve una upload session")
        return self._richiesta(
            "PUT",
            f"/drives/{drive_id}/items/{quote(cartella_id, safe='')}:"
            f"/{quote(file_locale.name, safe='')}:/content",
            headers={
                "Content-Type": (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            },
            contenuto=contenuto,
            timeout=180,
        ).json()
