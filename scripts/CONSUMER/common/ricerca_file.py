from __future__ import annotations

from pathlib import Path
from typing import Iterable


ESTENSIONI_EXCEL = (".xlsx", ".xlsm", ".xls")


def cerca_file(
    cartella: Path,
    parole: Iterable[str],
    *,
    estensioni: Iterable[str] = ESTENSIONI_EXCEL,
    ricorsiva: bool = False,
) -> list[Path]:
    """Cerca file per parole contenute nel nome, dal piu recente."""

    cartella = Path(cartella)
    if not cartella.is_dir():
        return []

    parole_normalizzate = [p.strip().casefold() for p in parole if p.strip()]
    estensioni_normalizzate = {e.casefold() for e in estensioni}
    candidati = cartella.rglob("*") if ricorsiva else cartella.glob("*")

    trovati = [
        file
        for file in candidati
        if file.is_file()
        and file.suffix.casefold() in estensioni_normalizzate
        and all(parola in file.stem.casefold() for parola in parole_normalizzate)
        and not file.name.startswith("~$")
    ]

    return sorted(trovati, key=lambda file: file.stat().st_mtime, reverse=True)


def cerca_file_unico(
    cartella: Path,
    parole: Iterable[str],
    *,
    estensioni: Iterable[str] = ESTENSIONI_EXCEL,
    ricorsiva: bool = False,
) -> Path:
    """Restituisce il file piu recente e segnala assenze o duplicati."""

    trovati = cerca_file(
        cartella,
        parole,
        estensioni=estensioni,
        ricorsiva=ricorsiva,
    )

    descrizione = " ".join(parole)
    if not trovati:
        raise FileNotFoundError(
            f"Nessun file contenente '{descrizione}' trovato in {cartella}"
        )

    if len(trovati) > 1:
        print(
            f"Attenzione: trovati {len(trovati)} file per '{descrizione}'. "
            f"Uso il piu recente: {trovati[0].name}"
        )

    return trovati[0]
