import csv
import json
from datetime import datetime
from pathlib import Path


CAMPI_LOG = [
    "timestamp",
    "azione",
    "stato_analisi",
    "azienda_crm_id",
    "ragione_sociale",
    "commerciale",
    "esito",
    "dettaglio",
]


def _valore_csv(valore):
    if valore is None:
        return ""

    if isinstance(valore, (dict, list)):
        return json.dumps(valore, ensure_ascii=False)

    return valore


def salva_log(log_entries: list[dict], cartella: Path) -> Path:
    cartella_log = Path(cartella) / "LOG"
    cartella_log.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_log = cartella_log / f"LOG_OPERAZIONI_{timestamp}.csv"

    with file_log.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CAMPI_LOG)
        writer.writeheader()

        for entry in log_entries:
            writer.writerow({
                campo: _valore_csv(entry.get(campo))
                for campo in CAMPI_LOG
            })

    return file_log
