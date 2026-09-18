from __future__ import annotations

import re
import tempfile
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from config import CROSS_SELLING, MAPPA_PEDONALITA


@contextmanager
def _workbook_compatibile(sorgente: Path | bytes):
    """Crea solo se necessario una copia con valori font OpenXML validi."""

    pattern = re.compile(rb'(<(?:\w+:)?family\b[^>]*\bval=")(\d+)(")')
    origine_zip = BytesIO(sorgente) if isinstance(sorgente, bytes) else sorgente
    with ZipFile(origine_zip, "r") as archivio:
        styles = archivio.read("xl/styles.xml")

    def sostituisci(match: re.Match[bytes]) -> bytes:
        valore = int(match.group(2))
        if valore <= 14:
            return match.group(0)
        return match.group(1) + b"2" + match.group(3)

    styles_corretti = pattern.sub(sostituisci, styles)
    if styles_corretti == styles:
        yield BytesIO(sorgente) if isinstance(sorgente, bytes) else sorgente
        return

    handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    temporaneo = Path(handle.name)
    handle.close()
    try:
        origine_zip = BytesIO(sorgente) if isinstance(sorgente, bytes) else sorgente
        with ZipFile(origine_zip, "r") as origine, ZipFile(
            temporaneo,
            "w",
            compression=ZIP_DEFLATED,
        ) as destinazione:
            for elemento in origine.infolist():
                contenuto = origine.read(elemento.filename)
                if elemento.filename == "xl/styles.xml":
                    contenuto = styles_corretti
                destinazione.writestr(elemento, contenuto)
        yield temporaneo
    finally:
        temporaneo.unlink(missing_ok=True)


def _testo(serie: pd.Series) -> pd.Series:
    return serie.astype("string").str.strip()


def _date(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, format="mixed", dayfirst=True, errors="coerce")


def _normalizza_negozio(serie: pd.Series) -> pd.Series:
    return (
        _testo(serie)
        .str.upper()
        .str.replace("_", " ", regex=False)
        .str.replace(r"\s+", " ", regex=True)
    )


def carica_business(file_remoto: dict, client_sharepoint) -> tuple[pd.DataFrame, pd.DataFrame]:
    contenuto = client_sharepoint.scarica_file(
        str(file_remoto["drive_id"]),
        str(file_remoto["id"]),
    )
    with _workbook_compatibile(contenuto) as workbook:
        raw = pd.read_excel(
            workbook,
            sheet_name="TRACCIAMENTO",
            engine="openpyxl",
        )
        riepilogo = pd.read_excel(
            workbook,
            sheet_name="INSERITO_NEGOZI",
            header=None,
            engine="openpyxl",
        )
    if raw.shape[1] < 17:
        raise ValueError("Il foglio TRACCIAMENTO non contiene le 17 colonne attese")

    df = raw.iloc[:, [0, 1, 3, 6, 7, 8, 9, 10, 12, 15, 16]].copy()
    df.columns = [
        "NEGOZIO",
        "VENDITORE",
        "DATA_INSERIMENTO",
        "DATA_ATTIVAZIONE",
        "FAMIGLIA_PRODOTTO",
        "PRODOTTO",
        "TIPO_ATTIVAZIONE",
        "QUANTITA",
        "PUNTI_INSERITI",
        "PUNTI_ATTIVATI",
        "UNITA_ATTIVATE",
    ]

    for colonna in ("NEGOZIO", "VENDITORE", "FAMIGLIA_PRODOTTO", "PRODOTTO", "TIPO_ATTIVAZIONE"):
        df[colonna] = _testo(df[colonna])
    df["NEGOZIO"] = _normalizza_negozio(df["NEGOZIO"])
    df["DATA_INSERIMENTO"] = _date(df["DATA_INSERIMENTO"])
    df["DATA_ATTIVAZIONE"] = _date(df["DATA_ATTIVAZIONE"])
    for colonna in ("QUANTITA", "PUNTI_INSERITI", "PUNTI_ATTIVATI", "UNITA_ATTIVATE"):
        df[colonna] = pd.to_numeric(df[colonna], errors="coerce").fillna(0)
    df = df[df["NEGOZIO"].notna() & df["NEGOZIO"].ne("")].copy()

    target = riepilogo.iloc[8:16, [1, 3]].copy()
    target.columns = ["NEGOZIO", "TARGET"]
    target["NEGOZIO"] = _normalizza_negozio(target["NEGOZIO"])
    target["TARGET"] = pd.to_numeric(target["TARGET"], errors="coerce")
    target = target[target["NEGOZIO"].notna()].drop_duplicates("NEGOZIO")
    return df, target


def carica_tracciamenti(
    file_remoti: dict[str, dict],
    client_sharepoint,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Legge il foglio unico TRACCIAMENTO e lo separa per attività."""

    frames = []
    colonne_attese = {
        "TRACCIAMENTO",
        "DATA INSERIMENTO",
        "VENDITORE",
        "OFFERTA / OFFERTA PROPOSTA",
    }
    for negozio, file_remoto in file_remoti.items():
        nome_file = str(file_remoto["name"])
        contenuto = client_sharepoint.scarica_file(
            str(file_remoto["drive_id"]),
            str(file_remoto["id"]),
        )
        df = pd.read_excel(
            BytesIO(contenuto),
            sheet_name="TRACCIAMENTO",
            engine="openpyxl",
        )
        df.columns = [str(col).strip().upper() for col in df.columns]
        mancanti = colonne_attese.difference(df.columns)
        if mancanti:
            raise ValueError(
                f"Colonne mancanti in {nome_file}: {', '.join(sorted(mancanti))}"
            )
        df["NEGOZIO"] = negozio
        frames.append(df)
        print(f"  OK {negozio}: scaricato e letto {nome_file}")

    base = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    colonne_base = ["NEGOZIO", "DATA", "VENDITORE", "DESCRIZIONE"]
    if base.empty:
        vuoto = pd.DataFrame(columns=colonne_base)
        return vuoto.copy(), vuoto.assign(CROSS_SELLING=pd.Series(dtype=bool)), vuoto.copy()

    base = base.rename(
        columns={
            "DATA INSERIMENTO": "DATA",
            "OFFERTA / OFFERTA PROPOSTA": "DESCRIZIONE",
        }
    )
    base["NEGOZIO"] = _normalizza_negozio(base["NEGOZIO"])
    base["VENDITORE"] = _testo(base["VENDITORE"])
    base["DATA"] = _date(base["DATA"])
    tipo = _testo(base["TRACCIAMENTO"]).str.upper()
    base = base[base["DATA"].notna()].copy()

    energia = base[tipo.loc[base.index].eq("TRATT_ENERGIA")][colonne_base].copy()
    gadget = base[tipo.loc[base.index].eq("GADGET")][colonne_base].copy()
    gadget["CROSS_SELLING"] = _testo(gadget["DESCRIZIONE"]).str.upper().ne(CROSS_SELLING)
    digi = base[tipo.loc[base.index].eq("DIGI")][colonne_base].copy()
    return energia, gadget, digi


def carica_pedonalita(file_remoto: dict, client_sharepoint) -> pd.DataFrame:
    contenuto = client_sharepoint.scarica_file(
        str(file_remoto["drive_id"]),
        str(file_remoto["id"]),
    )
    df = pd.read_parquet(BytesIO(contenuto))
    df.columns = [str(col).strip() for col in df.columns]
    if "Data" not in df.columns or "Negozio" not in df.columns or "Presenze" not in df.columns:
        raise ValueError("Il parquet pedonalita non contiene Data, Negozio e Presenze")
    df = df[["Data", "Negozio", "Presenze"]].copy()
    df.columns = ["DATA", "NEGOZIO", "PRESENZE"]
    df["DATA"] = _date(df["DATA"])
    df["NEGOZIO"] = _testo(df["NEGOZIO"]).map(MAPPA_PEDONALITA)
    df["PRESENZE"] = pd.to_numeric(df["PRESENZE"], errors="coerce").fillna(0)
    return df[df["DATA"].notna() & df["NEGOZIO"].notna()].copy()
