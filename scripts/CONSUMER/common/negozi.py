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


def carica_negozi() -> list[str]:
    
    """Restituisce l'elenco dei negozi configurati nel file JSON."""

    with FILE_NEGOZI.open("r", encoding="utf-8") as file:
        dati = json.load(file)
        
    
    negozi = dati.get("negozi")

    if not isinstance(negozi, list):
        raise ValueError(
            f"La chiave 'negozi' in {FILE_NEGOZI} deve contenere una lista"
        )
    
    negozi_validi = [
         negozio.strip() 
         for negozio in negozi 
         if isinstance(negozio, str) and negozio.strip()]

    if not negozi_validi:
        raise ValueError(
             f"nessun negozio valido configurato in {FILE_NEGOZI}"
        )
    

    return negozi_validi


def carica_codici_negozi() -> dict[str, str]:
    """Restituisce la corrispondenza tra codice colonna e nome negozio."""

    with FILE_NEGOZI.open("r", encoding="utf-8") as file:
        dati = json.load(file)

    codici_negozi = dati.get("codici_negozi")

    if not isinstance(codici_negozi, dict):
        raise ValueError(
            f"La chiave 'codici_negozi' in {FILE_NEGOZI} "
            "deve contenere un dizionario"
        )

    codici_validi = {
        codice.strip().upper(): negozio.strip().upper()
        for codice, negozio in codici_negozi.items()
        if (
            isinstance(codice, str)
            and codice.strip()
            and isinstance(negozio, str)
            and negozio.strip()
        )
    }

    if not codici_validi:
        raise ValueError(
            f"Nessun codice negozio valido configurato in {FILE_NEGOZI}"
        )

    return codici_validi



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
