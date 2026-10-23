"""Regole condivise per verificare e preparare i dati inclusi nell'installer.

Uso:
    python build_guard.py scripts

Il comando non modifica file: stampa l'inventario dei file ammessi e di quelli
esclusi. Menu.spec usa le stesse regole per costruire i dati PyInstaller.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

SELECTED_PATHS = (
    "config_env.py",
    "graph_sharepoint.py",
    "BUSINESS/common",
    "BUSINESS/config",
    "BUSINESS/02_(OLD)_APPUNTAMENTI_SETTIMANA",
    "BUSINESS/09_ESTRAZIONE_ORDINI_API",
    "BUSINESS/10_ESTRAZIONE_OPP_API",
    "BUSINESS/11_ESTRAZIONE_APP_API",
    "BUSINESS/12_FCST_BUSINESS",
    "BUSINESS/13_ESTRAI_FILE_GARA",
    "BUSINESS/14_ELABORA_CB",
    "BUSINESS/CAMPAGNE",
    "CONSUMER/common",
    "CONSUMER/config",
    "CONSUMER/01_FORMATTA_PEDONALITA",
    "CONSUMER/02_REPORT_PEDONALITA",
    "CONSUMER/03_FORMATTA_MAGAZZINO",
    "CONSUMER/11_CRUSCOTTO_AGGREGATIVO",
    "CONSUMER/12_CRUSCOTTO_PISTA_CONSUMER",
    "CONSUMER/13_REPORT_GIACENZE",
)

EXCLUDED_DIRECTORIES = frozenset({
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".nox", ".venv", "venv", "env", "node_modules",
    "build", "dist",
})
EXCLUDED_FILE_RE = re.compile(
    r"^(?:\.env(?:\..*)?|.*\.(?:pem|key|pfx|p12|p8|kdbx|pyc|pyo|tmp|bak|swp)"
    r"|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?"
    r"|(?:credentials?|secrets?|tokens?)(?:\..*)?"
    r"|(?:thumbs\.db|\.ds_store))$",
    re.IGNORECASE,
)


def exclusion_reason(path: Path, scripts_root: Path) -> str | None:
    """Restituisce il motivo di esclusione per un file sotto scripts_root."""
    relative = path.relative_to(scripts_root)
    for parent in relative.parts[:-1]:
        if parent.lower() in EXCLUDED_DIRECTORIES:
            return f"directory locale: {parent}"
    if EXCLUDED_FILE_RE.match(path.name):
        return f"file locale o credenziale: {path.name}"
    return None


def selected_files(scripts_root: Path) -> Iterable[Path]:
    """Elenca tutti i file delle sole aree richiamate dal menu."""
    for relative_path in SELECTED_PATHS:
        source = scripts_root / relative_path
        if not source.exists():
            raise FileNotFoundError(f"Risorsa richiesta dal menu non trovata: {source}")
        if source.is_file():
            yield source
        else:
            yield from (item for item in source.rglob("*") if item.is_file())


def inventory(scripts_root: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    allowed: list[Path] = []
    excluded: list[tuple[Path, str]] = []
    for item in selected_files(scripts_root):
        reason = exclusion_reason(item, scripts_root)
        if reason:
            excluded.append((item, reason))
        else:
            allowed.append(item)
    return allowed, excluded


def build_script_datas(scripts_root: Path) -> list[tuple[str, str]]:
    """Crea dati PyInstaller file-per-file, senza copie ricorsive non filtrate."""
    allowed, _ = inventory(scripts_root)
    return [
        (str(item), str(Path("scripts") / item.relative_to(scripts_root).parent))
        for item in allowed
    ]


def print_inventory(scripts_root: Path) -> int:
    allowed, excluded = inventory(scripts_root)
    print(f"Controllo installer: {len(allowed)} file ammessi.")
    if excluded:
        print(f"Controllo installer: {len(excluded)} file locali esclusi:")
        for item, reason in excluded:
            print(f" - {item.relative_to(scripts_root)} ({reason})")
    else:
        print("Controllo installer: nessun file locale da escludere.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verifica i file destinati all'installer.")
    parser.add_argument("scripts_root", nargs="?", default="scripts")
    args = parser.parse_args()
    raise SystemExit(print_inventory(Path(args.scripts_root).resolve()))
