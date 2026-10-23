"""Configurazione e accesso SharePoint per la divisione delle campagne."""

from __future__ import annotations

import os
import sys
from copy import copy
from pathlib import Path

BUSINESS_DIR = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = BUSINESS_DIR.parent
for directory in (SCRIPT_ROOT, BUSINESS_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from common.venditori import leggi_venditori
from graph_sharepoint import GraphSharePointClient

SHAREPOINT_HOSTNAME = os.getenv("SHAREPOINT_HOSTNAME", "").strip()
SHAREPOINT_SCAMBIO_SITE_PATH = os.getenv("SHAREPOINT_SCAMBIO_SITE_PATH", "").strip()
SHAREPOINT_SCAMBIO_LIBRARY_NAME = os.getenv("SHAREPOINT_SCAMBIO_LIBRARY_NAME", "").strip()
PATH_CAMPAGNE_REMOTO = os.getenv(
    "SHAREPOINT_BUSINESS_CAMPAGNE_FOLDER",
    "00_SCAMBIO DOCUMENTI/00_BUSINESS/CAMPAGNA",
).strip(" /")
PATH_OUTPUT_TEST = Path(__file__).resolve().parent / "OUTPUT_TEST"

_GRAPH_CLIENT = None
_DRIVE_SCAMBIO_ID = None
_DRIVE_VENDITORI = {}


def _client_graph():
    global _GRAPH_CLIENT
    if _GRAPH_CLIENT is None:
        _GRAPH_CLIENT = GraphSharePointClient()
    return _GRAPH_CLIENT


def _drive_scambio():
    global _DRIVE_SCAMBIO_ID
    configurazione = {
        "SHAREPOINT_HOSTNAME": SHAREPOINT_HOSTNAME,
        "SHAREPOINT_SCAMBIO_SITE_PATH": SHAREPOINT_SCAMBIO_SITE_PATH,
        "SHAREPOINT_SCAMBIO_LIBRARY_NAME": SHAREPOINT_SCAMBIO_LIBRARY_NAME,
        "SHAREPOINT_BUSINESS_CAMPAGNE_FOLDER": PATH_CAMPAGNE_REMOTO,
    }
    mancanti = [nome for nome, valore in configurazione.items() if not valore]
    if mancanti:
        raise ValueError("Configurazione SharePoint campagne incompleta: " + ", ".join(mancanti))
    if _DRIVE_SCAMBIO_ID is None:
        client = _client_graph()
        sito = client.trova_sito(SHAREPOINT_HOSTNAME, SHAREPOINT_SCAMBIO_SITE_PATH)
        raccolta = client.trova_raccolta_documenti(sito["id"], SHAREPOINT_SCAMBIO_LIBRARY_NAME)
        _DRIVE_SCAMBIO_ID = str(raccolta["id"])
    return _client_graph(), _DRIVE_SCAMBIO_ID


def trova_cartella_campagna_remota() -> str:
    """Trova la sottocartella con prefisso numerico piu alto."""
    client, drive_id = _drive_scambio()
    valide = []
    for elemento in client.elenca_elementi_cartella(drive_id, PATH_CAMPAGNE_REMOTO):
        if elemento.get("folder") is None:
            continue
        nome = str(elemento.get("name", ""))
        try:
            ordine = int(nome[:2])
        except ValueError:
            continue
        valide.append((ordine, nome))
    if not valide:
        raise FileNotFoundError(
            f"Nessuna sottocartella numerata trovata in {PATH_CAMPAGNE_REMOTO}"
        )
    _, nome = max(valide, key=lambda voce: (voce[0], voce[1]))
    return f"{PATH_CAMPAGNE_REMOTO}/{nome}"


def scarica_file_campagna(cartella_locale: Path) -> tuple[str, list[Path]]:
    """Scarica gli Excel presenti nell'ultima campagna SharePoint."""
    client, drive_id = _drive_scambio()
    cartella_remota = trova_cartella_campagna_remota()
    files = [
        file for file in client.elenca_file_cartella(drive_id, cartella_remota)
        if str(file.get("name", "")).casefold().endswith((".xlsx", ".xls"))
        and not str(file.get("name", "")).startswith("~$")
    ]
    if not files:
        raise FileNotFoundError(f"Nessun file Excel trovato in SharePoint: {cartella_remota}")
    cartella_locale.mkdir(parents=True, exist_ok=True)
    locali = []
    for file in files:
        locale = cartella_locale / str(file["name"])
        locale.write_bytes(client.scarica_file(drive_id, str(file["id"])))
        locali.append(locale)
    return cartella_remota, locali


def _normalizza_alias(valore: str) -> str:
    return " ".join(valore.casefold().replace(",", " ").split(" - ", 1)[0].split())


def trova_venditore(nome_agente: str) -> dict | None:
    """Risolve il testo Agente usando gli alias_cb del catalogo JSON."""
    cercato = _normalizza_alias(nome_agente)
    corrispondenze = []
    for venditore in leggi_venditori():
        alias = {_normalizza_alias(str(voce)) for voce in venditore.get("alias_cb", [])}
        alias.add(_normalizza_alias(str(venditore["nome_crm"])))
        if cercato in alias:
            corrispondenze.append(venditore)
    if len(corrispondenze) > 1:
        nomi = ", ".join(str(v["nome_crm"]) for v in corrispondenze)
        raise ValueError(f"Alias agente ambiguo {nome_agente!r}: {nomi}")
    return corrispondenze[0] if corrispondenze else None


def _destinazioni_venditore(venditore: dict) -> list[dict]:
    destinazioni = venditore.get("sharepoint_campagne_destinations")
    if destinazioni:
        return list(destinazioni)
    richiesti = ("sharepoint_site_path", "sharepoint_library", "sharepoint_campagne_folder")
    mancanti = [campo for campo in richiesti if not venditore.get(campo)]
    if mancanti:
        raise ValueError(
            f"Destinazione campagne non configurata per {venditore['nome_crm']}: "
            + ", ".join(mancanti)
        )
    return [{campo: venditore[campo] for campo in richiesti}]


def _drive_venditore(destinazione: dict):
    site_path = str(destinazione["sharepoint_site_path"])
    library = str(destinazione["sharepoint_library"])
    chiave = (site_path, library)
    if chiave not in _DRIVE_VENDITORI:
        client = _client_graph()
        sito = client.trova_sito(SHAREPOINT_HOSTNAME, site_path)
        raccolta = client.trova_raccolta_documenti(sito["id"], library)
        _DRIVE_VENDITORI[chiave] = str(raccolta["id"])
    return _client_graph(), _DRIVE_VENDITORI[chiave]


def pubblica_campagna(venditore: dict, file_locale: Path, *, test: bool) -> None:
    """Sostituisce i file CAMPAGNA del venditore, o descrive l'azione in TEST."""
    for destinazione in _destinazioni_venditore(venditore):
        cartella = str(destinazione["sharepoint_campagne_folder"])
        etichetta = f"{destinazione['sharepoint_site_path']} / {cartella}"
        if test:
            print(f"  [TEST] Caricherebbe {file_locale.name} in {etichetta}")
            continue
        client, drive_id = _drive_venditore(destinazione)
        esistenti = client.elenca_file_cartella(drive_id, cartella, crea=True)
        for remoto in esistenti:
            if "campagna" in str(remoto.get("name", "")).casefold():
                client.elimina_file(drive_id, str(remoto["id"]), str(remoto.get("eTag", "")))
        client.carica_bytes(
            drive_id,
            cartella,
            file_locale.name,
            file_locale.read_bytes(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        print(f"  OK Pubblicato in {etichetta}")


def pubblica_campagne_divise(
    files_locali: list[Path],
    cartella_campagna: str,
    *,
    test: bool,
) -> str:
    """Salva tutti gli output nella sottocartella centrale CAMPAGNE_DIVISE."""
    destinazione = f"{cartella_campagna.rstrip('/')}/CAMPAGNE_DIVISE"
    if test:
        print(f"\n[TEST] Cartella centrale: {destinazione}")
        for file in files_locali:
            print(f"  [TEST] Caricherebbe {file.name}")
        return destinazione

    client, drive_id = _drive_scambio()
    esistenti = client.elenca_file_cartella(drive_id, destinazione, crea=True)
    for remoto in esistenti:
        if str(remoto.get("name", "")).casefold().endswith(".xlsx"):
            client.elimina_file(
                drive_id, str(remoto["id"]), str(remoto.get("eTag", ""))
            )
    for file in files_locali:
        client.carica_bytes(
            drive_id,
            destinazione,
            file.name,
            file.read_bytes(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
    print(f"\nOK {len(files_locali)} file salvati in {destinazione}")
    return destinazione


def copia_stile_cella(cella_origine, cella_destinazione):
    if cella_origine.has_style:
        cella_destinazione.font = copy(cella_origine.font)
        cella_destinazione.border = copy(cella_origine.border)
        cella_destinazione.fill = copy(cella_origine.fill)
        cella_destinazione.number_format = copy(cella_origine.number_format)
        cella_destinazione.protection = copy(cella_origine.protection)
        cella_destinazione.alignment = copy(cella_origine.alignment)
