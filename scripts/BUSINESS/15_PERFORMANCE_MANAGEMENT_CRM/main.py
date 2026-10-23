from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import OUTPUT_DIR, TIMEZONE, carica_venditori
from crm_client import CrmClient
from regole import applica_regole
from template_email import genera_email, genera_mjml


def _nome_file(nome: str) -> str:
    pulito = re.sub(r"[^A-Za-z0-9._-]+", "_", nome).strip("._")
    return pulito or "non_assegnato"


def _serializza(valore):
    if isinstance(valore, (date, datetime)):
        return valore.isoformat()
    raise TypeError(f"Tipo non serializzabile: {type(valore).__name__}")


def esegui(oggi: date | None = None, output_dir: Path | None = None) -> Path:
    istante = datetime.now(ZoneInfo(TIMEZONE))
    oggi = oggi or istante.date()
    destinazione = output_dir or OUTPUT_DIR / istante.strftime("%Y-%m-%d_%H%M%S")
    destinazione.mkdir(parents=True, exist_ok=False)

    client = CrmClient()
    try:
        opportunita = client.estrai_opportunita()
        appuntamenti = client.estrai_appuntamenti()
    except Exception as errore:
        audit = {
            "esito": "interrotto_dati_parziali",
            "data_riferimento": oggi.isoformat(),
            "errore": str(errore),
            "nota": "Nessuna anteprima commerciale generata.",
        }
        (destinazione / "audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise

    risultati = applica_regole(opportunita, appuntamenti, oggi, carica_venditori())
    anteprime = []
    conteggi = {}
    for commerciale, sezioni in sorted(risultati.items()):
        conteggio = sum(len(elementi) for elementi in sezioni.values())
        conteggi[commerciale] = {nome: len(elementi) for nome, elementi in sezioni.items()}
        if commerciale != "__NON_ASSEGNATO__" and conteggio:
            nome_file = f"email_{_nome_file(commerciale)}.html"
            nome_mjml = f"email_{_nome_file(commerciale)}.mjml"
            (destinazione / nome_mjml).write_text(
                genera_mjml(commerciale, sezioni, oggi), encoding="utf-8"
            )
            (destinazione / nome_file).write_text(
                genera_email(commerciale, sezioni, oggi), encoding="utf-8"
            )
            anteprime.append(nome_file)

    non_assegnati = risultati.get("__NON_ASSEGNATO__")
    anomalie_amministrative = {
        "record_non_assegnati": non_assegnati or {},
        "anagrafiche_non_recuperabili": client.anomalie_anagrafiche,
    }
    if non_assegnati or client.anomalie_anagrafiche:
        (destinazione / "anomalie_amministrative.json").write_text(
            json.dumps(anomalie_amministrative, ensure_ascii=False, indent=2, default=_serializza),
            encoding="utf-8",
        )

    audit = {
        "esito": "completato_dry_run",
        "data_riferimento": oggi.isoformat(),
        "opportunita_lette": len(opportunita),
        "appuntamenti_letti": len(appuntamenti),
        "anteprime_generate": anteprime,
        "conteggi": conteggi,
        "anomalie_anagrafiche": len(client.anomalie_anagrafiche),
        "nota": "Nessuna e-mail inviata e nessuna modifica effettuata nel CRM.",
    }
    (destinazione / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destinazione


def main() -> int:
    parser = argparse.ArgumentParser(description="MVP locale Performance Management CRM")
    parser.add_argument(
        "--data",
        type=date.fromisoformat,
        help="Data di riferimento YYYY-MM-DD; predefinita: oggi Europe/Rome",
    )
    argomenti = parser.parse_args()
    try:
        destinazione = esegui(argomenti.data)
    except Exception as errore:
        print(f"ERRORE: pipeline interrotta: {errore}", file=sys.stderr)
        return 1
    print(f"Dry-run completato. Risultati: {destinazione}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

