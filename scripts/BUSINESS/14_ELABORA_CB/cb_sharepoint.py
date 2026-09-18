from pathlib import Path

from config import (
    PATH_CB_CORRENTE,
    PATH_CB_CORRENTE_REMOTO,
    PATH_CB_STORICO_REMOTO,
    PATH_CB_TEMP,
    PATH_RAW_CB,
    PATH_RAW_CB_REMOTO,
    SHAREPOINT_HOSTNAME,
    SHAREPOINT_SCAMBIO_LIBRARY_NAME,
    SHAREPOINT_SCAMBIO_SITE_PATH,
)
from graph_sharepoint import GraphSharePointClient


_CLIENT = None
_DRIVE_ID = None


def _drive():
    global _CLIENT, _DRIVE_ID
    configurazione = {
        "SHAREPOINT_HOSTNAME": SHAREPOINT_HOSTNAME,
        "SHAREPOINT_SCAMBIO_SITE_PATH": SHAREPOINT_SCAMBIO_SITE_PATH,
        "SHAREPOINT_SCAMBIO_LIBRARY_NAME": SHAREPOINT_SCAMBIO_LIBRARY_NAME,
        "SHAREPOINT_BUSINESS_CB_FOLDER": PATH_CB_CORRENTE_REMOTO,
    }
    mancanti = [nome for nome, valore in configurazione.items() if not valore]
    if mancanti:
        raise ValueError("Configurazione SharePoint CB incompleta: " + ", ".join(mancanti))
    if _CLIENT is None:
        _CLIENT = GraphSharePointClient()
        sito = _CLIENT.trova_sito(SHAREPOINT_HOSTNAME, SHAREPOINT_SCAMBIO_SITE_PATH)
        raccolta = _CLIENT.trova_raccolta_documenti(
            sito["id"], SHAREPOINT_SCAMBIO_LIBRARY_NAME
        )
        _DRIVE_ID = str(raccolta["id"])
    return _CLIENT, _DRIVE_ID


def _file_dati(elemento: dict) -> bool:
    nome = str(elemento.get("name", "")).casefold()
    return nome.endswith((".xlsx", ".xls", ".csv", ".parquet"))


def scarica_file_raw(*, rapido: bool = False) -> Path:
    client, drive_id = _drive()
    files = [
        file for file in client.elenca_file_cartella(drive_id, PATH_RAW_CB_REMOTO)
        if _file_dati(file)
    ]
    if rapido and len(files) != 1:
        raise ValueError(
            "La modalita rapida richiede esattamente un file dati in "
            f"{PATH_RAW_CB_REMOTO}; trovati: {len(files)}."
        )
    if not rapido:
        files = [file for file in files if "cb" in str(file.get("name", "")).casefold()]
    if not files:
        raise FileNotFoundError(f"Nessun file CB trovato in {PATH_RAW_CB_REMOTO}")
    files.sort(key=lambda file: str(file.get("lastModifiedDateTime", "")), reverse=True)
    scelto = files[0]
    PATH_RAW_CB.mkdir(parents=True, exist_ok=True)
    locale = PATH_RAW_CB / str(scelto["name"])
    locale.write_bytes(client.scarica_file(drive_id, str(scelto["id"])))
    return locale


def archivia_correnti() -> str | None:
    client, drive_id = _drive()
    files = client.elenca_file_cartella(drive_id, PATH_CB_CORRENTE_REMOTO, crea=True)
    if not files:
        return None
    originale = next(
        (
            file for file in files
            if "cb" in str(file.get("name", "")).casefold()
            and "pulita" not in str(file.get("name", "")).casefold()
        ),
        None,
    )
    if originale is None:
        raise FileNotFoundError("In 01_CORRENTE non è stato trovato il vecchio CB originale")
    destinazione = f"{PATH_CB_STORICO_REMOTO}/{Path(str(originale['name'])).stem}"
    cartella = client.crea_percorso_cartelle(drive_id, destinazione)
    presenti = {
        str(file.get("name", "")).casefold()
        for file in client.elenca_file_cartella(drive_id, destinazione)
    }
    duplicati = [file["name"] for file in files if str(file["name"]).casefold() in presenti]
    if duplicati:
        raise FileExistsError(f"File già presenti in {destinazione}: {duplicati}")
    for file in files:
        client.sposta_elemento(drive_id, str(file["id"]), str(cartella["id"]))
    return destinazione


def carica_file(percorso_locale: Path, cartella_remota: str) -> dict:
    percorso_locale = Path(percorso_locale)
    client, drive_id = _drive()
    content_type = "application/octet-stream"
    if percorso_locale.suffix.casefold() == ".xlsx":
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif percorso_locale.suffix.casefold() == ".html":
        content_type = "text/html; charset=utf-8"
    elif percorso_locale.suffix.casefold() in {".txt", ".csv"}:
        content_type = "text/plain; charset=utf-8"
    return client.carica_bytes(
        drive_id,
        cartella_remota,
        percorso_locale.name,
        percorso_locale.read_bytes(),
        content_type=content_type,
    )


def sincronizza_output_temporanei() -> list[dict]:
    caricati = []
    mappa = {
        PATH_RAW_CB: PATH_RAW_CB_REMOTO,
        PATH_CB_CORRENTE: PATH_CB_CORRENTE_REMOTO,
    }
    for radice_locale, radice_remota in mappa.items():
        if not radice_locale.exists():
            continue
        for file in radice_locale.rglob("*"):
            if not file.is_file():
                continue
            relativo = file.parent.relative_to(radice_locale).as_posix()
            cartella = radice_remota if relativo == "." else f"{radice_remota}/{relativo}"
            caricati.append(carica_file(file, cartella))
    return caricati
