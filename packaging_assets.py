"""Explicit operational resource allowlist: never collect data/output directories."""
from pathlib import Path

RESOURCES = {
    "scripts/BUSINESS/config/venditori.json",
    "scripts/CONSUMER/config/negozi.json",
    "scripts/BUSINESS/14_ELABORA_CB/mappatura_colonne_cb.json",
    "scripts/BUSINESS/14_ELABORA_CB/mappatura_consistenze.json",
    "scripts/BUSINESS/15_PERFORMANCE_MANAGEMENT_CRM/logo MWR.jpg",
    "scripts/BUSINESS/15_PERFORMANCE_MANAGEMENT_CRM/package.json",
    "scripts/BUSINESS/15_PERFORMANCE_MANAGEMENT_CRM/package-lock.json",
    "scripts/BUSINESS/02_(OLD)_APPUNTAMENTI_SETTIMANA/TEMPLATE/TEMPLATE.xlsx",
    "scripts/CONSUMER/02_REPORT_PEDONALITA/TEMPLATE/TEMPLATE_PEDONALITA.xlsx",
}


def script_assets(entries, root):
    root = Path(root)
    result = []
    for source, destination in entries:
        path = root / source
        if path.is_file():
            result.append((str(path), destination))
            continue
        for file in sorted(path.rglob("*")):
            relative = file.relative_to(root).as_posix()
            if not file.is_file() or any(part in {"__pycache__", "output", "tests", "prove", ".git"} for part in file.parts):
                continue
            if file.name.startswith("test_") or file.name == "prova.py":
                continue
            if file.suffix == ".py" or relative in RESOURCES:
                result.append((str(file), str(Path(destination) / file.relative_to(path).parent)))
    return result
