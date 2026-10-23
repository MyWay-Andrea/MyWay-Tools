import json
from pathlib import Path
import pandas as pd 
from colorama import Fore, init
init(autoreset=True)

'''
File per creare una funzione riutilizzabile da tutti gli script, in modo tale da non ripeterla n volte
e creare una struttura solida e scalabile nel tempo

crezione: 16/07/2026 Andrea Gisoli
'''


PATH_DIR = Path(__file__).parents[1]

#json negozi
FILE_NEGOZI = PATH_DIR.resolve() / "config" / "negozi.json"

# cartella sincronizzata Teams
PATH_SHAREPOINT = Path.home() / "My Way S.r.l"

#cartella CONSUMER Teams
PATH_TEAM_CONSUMER = PATH_SHAREPOINT / "TEAM CONSUMER - TEAM CONSUMER"


def leggi_negozi() -> list[dict[str, str]]:
    """Legge e valida l'anagrafica unica dei negozi."""

    with FILE_NEGOZI.open("r", encoding="utf-8") as file:
        dati = json.load(file)

    negozi = dati.get("negozi")
    if not isinstance(negozi, list):
        raise ValueError(
            f"La chiave 'negozi' in {FILE_NEGOZI} deve contenere una lista"
        )

    risultato = []
    nomi_visti = set()
    alias_visti = set()
    dealer_visti = set()

    for posizione, negozio in enumerate(negozi, start=1):
        if not isinstance(negozio, dict):
            raise ValueError(
                f"Il negozio in posizione {posizione} in {FILE_NEGOZI} "
                "deve essere un dizionario"
            )

        nome = negozio.get("nome")
        alias = negozio.get("alias")
        codice_dealer = negozio.get("codice_dealer")
        nomi_storici = negozio.get("nomi_storici", [])

        if not isinstance(nome, str) or not nome.strip():
            raise ValueError(f"Nome negozio non valido in {FILE_NEGOZI}: {nome!r}")
        if not isinstance(alias, str) or not alias.strip():
            raise ValueError(
                f"Alias non valido per il negozio {nome!r} in {FILE_NEGOZI}"
            )
        if codice_dealer is not None and (
            not isinstance(codice_dealer, str) or not codice_dealer.strip()
        ):
            raise ValueError(
                f"Codice dealer non valido per il negozio {nome!r} in {FILE_NEGOZI}"
            )
        if not isinstance(nomi_storici, list) or any(
            not isinstance(valore, str) or not valore.strip()
            for valore in nomi_storici
        ):
            raise ValueError(
                f"Nomi storici non validi per il negozio {nome!r} in {FILE_NEGOZI}"
            )

        record = {
            "nome": nome.strip().upper(),
            "alias": alias.strip().upper(),
        }
        if codice_dealer is not None:
            record["codice_dealer"] = codice_dealer.strip().upper()
        if nomi_storici:
            record["nomi_storici"] = [valore.strip() for valore in nomi_storici]

        if record["nome"] in nomi_visti:
            raise ValueError(f"Nome negozio duplicato: {record['nome']}")
        if record["alias"] in alias_visti:
            raise ValueError(f"Alias negozio duplicato: {record['alias']}")
        if record.get("codice_dealer") in dealer_visti:
            raise ValueError(f"Codice dealer duplicato: {record['codice_dealer']}")

        nomi_visti.add(record["nome"])
        alias_visti.add(record["alias"])
        if "codice_dealer" in record:
            dealer_visti.add(record["codice_dealer"])
        risultato.append(record)

    if not risultato:
        raise ValueError(f"Nessun negozio valido configurato in {FILE_NEGOZI}")

    return risultato


def carica_negozi() -> list[str]:
    """Restituisce, nell'ordine configurato, i nomi dei negozi."""

    return [negozio["nome"] for negozio in leggi_negozi()]


def carica_codici_negozi() -> dict[str, str]:
    """Restituisce la corrispondenza alias-nome negozio."""

    return {negozio["alias"]: negozio["nome"] for negozio in leggi_negozi()}


def carica_codici_dealer_pedonalita() -> dict[str, str]:
    """Restituisce la corrispondenza tra codice dealer e sede pedonalita."""

    codici_validi = {
        negozio["codice_dealer"]: negozio["nome"]
        for negozio in leggi_negozi()
        if "codice_dealer" in negozio
    }

    if not codici_validi:
        raise ValueError(
            f"Nessun codice dealer valido configurato in {FILE_NEGOZI}"
        )

    return codici_validi


def normalizza_nomi_negozi(df: pd.DataFrame) -> pd.DataFrame:
    """Converte nel nome canonico gli eventuali nomi negozio storici."""

    if "Negozio" not in df.columns:
        raise ValueError("Colonna 'Negozio' non presente nel dataframe")

    mappa = {}
    for negozio in leggi_negozi():
        nome = negozio["nome"]
        mappa[nome.casefold()] = nome
        for nome_storico in negozio.get("nomi_storici", []):
            mappa[nome_storico.casefold()] = nome

    risultato = df.copy()
    valori = risultato["Negozio"].astype("string").str.strip()
    nomi_normalizzati = valori.str.casefold().map(mappa)
    risultato["Negozio"] = valori.where(nomi_normalizzati.isna(), nomi_normalizzati)
    return risultato



def trova_cartelle_negozi() -> dict[str, Path]:
    """Restituisce negozio e percorso della relativa cartella SharePoint."""

    cartelle_trovate = {}

    for negozio in carica_negozi():
        percorso_cartella = PATH_SHAREPOINT / f"TEAM - {negozio} - TEAM - {negozio}"

        if percorso_cartella.is_dir():
            cartelle_trovate[negozio] = percorso_cartella
        else:
            print(f"✕ Cartella non trovata: {percorso_cartella}")

    return cartelle_trovate


def estrai_df(path_files: dict[str, Path]) -> pd.DataFrame:
    
    lista_df = []

    for negozio, path in path_files.items():
        df = pd.read_excel(path, dtype = str, engine = "openpyxl")
        df.columns = [col.strip() for col in df.columns]
        df["NEGOZIO"] = negozio
        df.insert(0, "NEGOZIO", df.pop("NEGOZIO"))
            
        lista_df.append(df)

        print(Fore.GREEN + " ✓  " + Fore.RESET + f"{negozio}: lette {len(df)} righe")

    if not lista_df:
        print(Fore.RED + " ✕  Nessun file da aggregare")
        return pd.DataFrame()
    
    df_aggregato = pd.concat(lista_df, ignore_index = True)
    
    df_formattato = _formatta_df(df_aggregato)

    print(f"\nTotale righe aggregate: {len(df_aggregato)}")

    return df_formattato


def _formatta_df(df: pd.DataFrame) -> pd.DataFrame:
    """Formatta dinamicamente le colonne in base al loro nome."""

    df_formattato = df.copy()

    for col in df_formattato.columns:
        col_name = str(col).strip().lower()

        if "data" in col_name:
            originali_non_vuoti = df_formattato[col].notna()

            convertite = pd.to_datetime(
                df_formattato[col],
                format="mixed",
                dayfirst=True,
                errors="coerce",
            )

            non_riconosciute = originali_non_vuoti & convertite.isna()

            if non_riconosciute.any():
                print(
                    f"Attenzione: {non_riconosciute.sum()} date non riconosciute "
                    f"nella colonna {col}"
                )

            df_formattato[col] = convertite
        
        elif "qt" in col_name or "quantit" in col_name:
            df_formattato[col] = pd.to_numeric(
                df_formattato[col],
                errors="coerce",
            )
        
        else:
            df_formattato[col] = df_formattato[col].astype("string")

    return df_formattato
