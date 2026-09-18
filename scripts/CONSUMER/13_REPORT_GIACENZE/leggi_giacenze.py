from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path

import pandas as pd


def carica_codici_negozi(file_negozi: Path) -> dict[str, str]:
    """Legge e valida la mappatura codice-negozio mantenendo l'ordine del JSON."""

    file_negozi = Path(file_negozi)
    with file_negozi.open("r", encoding="utf-8") as file:
        configurazione = json.load(file)

    codici_negozi = configurazione.get("codici_negozi")
    if not isinstance(codici_negozi, dict):
        raise ValueError(
            f"La chiave 'codici_negozi' in {file_negozi} deve essere un dizionario"
        )

    risultato: dict[str, str] = {}
    for codice, negozio in codici_negozi.items():
        if not isinstance(codice, str) or not codice.strip():
            raise ValueError(f"Codice negozio non valido in {file_negozi}: {codice!r}")
        if not isinstance(negozio, str) or not negozio.strip():
            raise ValueError(
                f"Nome negozio non valido per il codice {codice!r} in {file_negozi}"
            )

        codice_normalizzato = codice.strip().upper()
        if codice_normalizzato in risultato:
            raise ValueError(
                f"Codice negozio duplicato in {file_negozi}: {codice_normalizzato}"
            )
        risultato[codice_normalizzato] = negozio.strip()

    if not risultato:
        raise ValueError(f"Nessun codice negozio configurato in {file_negozi}")

    return risultato


def trova_file_giacenze(
    cartella_raw: Path,
    parole_chiave: tuple[str, ...] = ("GIACENZE_ARTICOLI",),
) -> Path:
    """Trova il file Excel di giacenza più recente nella cartella RAW."""

    cartella_raw = Path(cartella_raw)
    if not cartella_raw.is_dir():
        raise FileNotFoundError(f"Cartella RAW non trovata: {cartella_raw}")

    parole = tuple(parola.strip().casefold() for parola in parole_chiave if parola)
    candidati = [
        file
        for file in cartella_raw.iterdir()
        if file.is_file()
        and file.suffix.casefold() in {".xlsx", ".xlsm"}
        and not file.name.startswith("~$")
        and all(parola in file.stem.casefold() for parola in parole)
    ]

    if not candidati:
        descrizione = " ".join(parole_chiave)
        raise FileNotFoundError(
            f"Nessun file contenente '{descrizione}' trovato in {cartella_raw}"
        )

    candidati.sort(key=lambda file: file.stat().st_mtime, reverse=True)
    if len(candidati) > 1:
        print(
            f"ATTENZIONE: trovati {len(candidati)} file di giacenza in "
            f"{cartella_raw}. Uso il più recente: {candidati[0].name}"
        )

    return candidati[0]


def _normalizza_intestazione(valore: object) -> str:
    if valore is None or pd.isna(valore):
        return ""
    return re.sub(r"\s+", " ", str(valore).strip()).upper()


def _trova_foglio_e_intestazione(
    file_excel: Path | bytes,
    nome_file: str,
    intestazione_codice: str,
    intestazione_descrizione: str,
) -> tuple[str, int]:
    richieste = {
        _normalizza_intestazione(intestazione_codice),
        _normalizza_intestazione(intestazione_descrizione),
    }

    sorgente_excel = BytesIO(file_excel) if isinstance(file_excel, bytes) else file_excel
    with pd.ExcelFile(sorgente_excel, engine="openpyxl") as excel:
        corrispondenze: list[tuple[str, int]] = []
        for nome_foglio in excel.sheet_names:
            anteprima = pd.read_excel(
                excel,
                sheet_name=nome_foglio,
                header=None,
                nrows=25,
                dtype=object,
            )
            for indice_riga, riga in anteprima.iterrows():
                valori = {_normalizza_intestazione(valore) for valore in riga}
                if richieste.issubset(valori):
                    corrispondenze.append((nome_foglio, int(indice_riga)))
                    break

    if not corrispondenze:
        raise ValueError(
            f"Nessun foglio di dettaglio trovato in {nome_file}: "
            f"mancano le intestazioni {sorted(richieste)}"
        )
    if len(corrispondenze) > 1:
        nomi = ", ".join(nome for nome, _ in corrispondenze)
        raise ValueError(
            f"Più fogli contengono le intestazioni del dettaglio in "
            f"{nome_file}: {nomi}"
        )

    return corrispondenze[0]


def estrai_dataframe_giacenze(
    file_excel: Path | bytes,
    codici_negozi: dict[str, str],
    *,
    nome_file: str | None = None,
    intestazione_codice: str = "Cod.Art.",
    intestazione_descrizione: str = "Descrizione",
    suffisso_giacenza: str = "GIAC.",
    intestazione_totale: str = "TOT. GIAC.",
    intestazione_totale_valore: str = "TOT. VAL.",
) -> pd.DataFrame:
    """Estrae il DataFrame pronto per la futura creazione del report.

    Le celle di giacenza vuote diventano ``'-'``. I valori presenti, compresi
    quelli negativi, restano numerici. Le colonne negozio non configurate nel
    JSON vengono ignorate; i codici JSON assenti nell'Excel sono segnalati.
    """

    if isinstance(file_excel, bytes):
        if not file_excel:
            raise ValueError("Il contenuto Excel scaricato è vuoto")
        nome_sorgente = nome_file or "file_giacenze.xlsx"
    else:
        file_excel = Path(file_excel)
        if not file_excel.is_file():
            raise FileNotFoundError(f"File Excel non trovato: {file_excel}")
        nome_sorgente = nome_file or file_excel.name

    nome_foglio, riga_intestazione = _trova_foglio_e_intestazione(
        file_excel,
        nome_sorgente,
        intestazione_codice,
        intestazione_descrizione,
    )
    sorgente_excel = BytesIO(file_excel) if isinstance(file_excel, bytes) else file_excel
    sorgente = pd.read_excel(
        sorgente_excel,
        sheet_name=nome_foglio,
        header=riga_intestazione,
        dtype=object,
        engine="openpyxl",
    )

    colonne_normalizzate: dict[str, object] = {}
    duplicati: set[str] = set()
    for colonna in sorgente.columns:
        normalizzata = _normalizza_intestazione(colonna)
        if not normalizzata:
            continue
        if normalizzata in colonne_normalizzate:
            duplicati.add(normalizzata)
        colonne_normalizzate[normalizzata] = colonna
    if duplicati:
        raise ValueError(
            "Intestazioni duplicate dopo la normalizzazione: "
            + ", ".join(sorted(duplicati))
        )

    codice_normalizzato = _normalizza_intestazione(intestazione_codice)
    descrizione_normalizzata = _normalizza_intestazione(intestazione_descrizione)
    for richiesta in (codice_normalizzato, descrizione_normalizzata):
        if richiesta not in colonne_normalizzate:
            raise ValueError(
                f"Colonna obbligatoria '{richiesta}' assente in {nome_sorgente}"
            )

    suffisso_normalizzato = _normalizza_intestazione(suffisso_giacenza)
    totale_normalizzato = _normalizza_intestazione(intestazione_totale)
    totale_valore_normalizzato = _normalizza_intestazione(
        intestazione_totale_valore
    )
    if totale_valore_normalizzato not in colonne_normalizzate:
        raise ValueError(
            f"Colonna obbligatoria '{totale_valore_normalizzato}' assente "
            f"in {nome_sorgente}"
        )
    colonne_giacenza_excel: dict[str, object] = {}
    for normalizzata, originale in colonne_normalizzate.items():
        if normalizzata == totale_normalizzato:
            continue
        parti = normalizzata.split(" ", 1)
        if len(parti) == 2 and parti[1] == suffisso_normalizzato:
            colonne_giacenza_excel[parti[0]] = originale

    codici_configurati = list(codici_negozi)
    codici_mancanti = [
        codice for codice in codici_configurati if codice not in colonne_giacenza_excel
    ]
    for codice in codici_mancanti:
        print(
            f"ATTENZIONE: negozio {codice} ({codici_negozi[codice]}) presente "
            f"in negozi.json ma colonna '{codice} {suffisso_giacenza}' assente "
            f"in {nome_sorgente}."
        )

    codici_extra_excel = [
        codice
        for codice in colonne_giacenza_excel
        if codice not in codici_negozi
    ]
    if codici_extra_excel:
        print(
            "INFO: colonne negozio presenti solo nel file Excel e ignorate: "
            + ", ".join(codici_extra_excel)
        )

    codici_presenti = [
        codice for codice in codici_configurati if codice in colonne_giacenza_excel
    ]
    if not codici_presenti:
        raise ValueError(
            f"Nessuna colonna di giacenza configurata trovata in {nome_sorgente}"
        )

    colonna_codice = colonne_normalizzate[codice_normalizzato]
    colonna_descrizione = colonne_normalizzate[descrizione_normalizzata]
    colonna_totale_valore = colonne_normalizzate[totale_valore_normalizzato]

    # Rimuove solo righe completamente vuote e la riga riepilogativa finale.
    # Una riga articolo priva di codice non deve essere scartata silenziosamente.
    righe_vuote = sorgente.isna().all(axis=1)
    righe_totale = sorgente[colonna_codice].isna() & sorgente[
        colonna_descrizione
    ].isna()
    if totale_normalizzato in colonne_normalizzate:
        colonna_totale = colonne_normalizzate[totale_normalizzato]
        righe_totale &= sorgente[colonna_totale].notna()
    else:
        righe_totale &= False
    sorgente = sorgente.loc[~righe_vuote & ~righe_totale].copy()

    colonne_da_leggere = [
        colonna_codice,
        colonna_descrizione,
        *(colonne_giacenza_excel[codice] for codice in codici_presenti),
        colonna_totale_valore,
    ]
    risultato = sorgente.loc[:, colonne_da_leggere].copy()
    risultato.columns = ["cod.art", "descrizione", *codici_presenti, "valore"]

    risultato["cod.art"] = risultato["cod.art"].astype("string").str.strip()
    risultato["descrizione"] = risultato["descrizione"].astype("string").str.strip()

    codici_vuoti = risultato["cod.art"].isna() | risultato["cod.art"].eq("")
    descrizioni_vuote = (
        risultato["descrizione"].isna() | risultato["descrizione"].eq("")
    )
    if codici_vuoti.any():
        raise ValueError(f"Trovati {int(codici_vuoti.sum())} codici articolo vuoti")
    if descrizioni_vuote.any():
        raise ValueError(f"Trovate {int(descrizioni_vuote.sum())} descrizioni vuote")

    duplicati_articolo = risultato.loc[
        risultato["cod.art"].duplicated(keep=False), "cod.art"
    ].unique()
    if len(duplicati_articolo):
        raise ValueError(
            "Codici articolo duplicati: "
            + ", ".join(str(codice) for codice in duplicati_articolo)
        )

    for codice in codici_presenti:
        valori_originali = risultato[codice]
        valori_numerici = pd.to_numeric(valori_originali, errors="coerce")
        non_numerici = valori_originali.notna() & valori_numerici.isna()
        if non_numerici.any():
            articoli = risultato.loc[non_numerici, "cod.art"].tolist()
            raise ValueError(
                f"Valori non numerici nella colonna {codice} per gli articoli: "
                + ", ".join(str(articolo) for articolo in articoli)
            )
        risultato[codice] = valori_numerici.astype(object).where(
            valori_numerici.notna(), "-"
        )

    valori_originali = risultato["valore"]
    valori_numerici = pd.to_numeric(valori_originali, errors="coerce")
    non_numerici = valori_originali.notna() & valori_numerici.isna()
    if non_numerici.any():
        articoli = risultato.loc[non_numerici, "cod.art"].tolist()
        raise ValueError(
            "Valori non numerici nella colonna TOT. VAL. per gli articoli: "
            + ", ".join(str(articolo) for articolo in articoli)
        )
    risultato["valore"] = valori_numerici.astype(object).where(
        valori_numerici.notna(), "-"
    )

    return risultato.reset_index(drop=True)
