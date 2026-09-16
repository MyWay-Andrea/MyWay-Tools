import pandas as pd
import re
from config import trova_file, PATH_RAW_FOLDER, salva_su_teams, PATH_TEAMS, elimina_file_teams, elimina_file_RAW 

def categorizza(codice: str, descrizione):
    """
    Restituisce la categoria in base al codice e alla descrizione dell"articolo.
    """
    codice = str(codice).strip()
    descrizione = str(descrizione).strip().upper()
    if re.search(r"RESO", codice, re.IGNORECASE):
        return "RESO"
    
    if re.match(r"DE", descrizione, re.IGNORECASE) or re.search(r"DEMO", descrizione, re.IGNORECASE):
        return "DEMO"

    if re.match(r'^1900\d+$', codice) or re.search(r'ROUTER', descrizione,  re.IGNORECASE) or re.search(r'WIFI', descrizione,  re.IGNORECASE): 
        return "FISSA"
    
    if re.match(r'^13\d+$', codice) and "WEARABLE" not in descrizione:
        return "TELEFONIA"
    
    if re.match(r'^9700\d+$', codice): 
        return "KASKO"
    
    if re.match(r'^82\d+$', codice) or re.match(r'O-82\d+$', codice) or re.search(r"SIM", descrizione, re.IGNORECASE): 
        return "SIM"
    
    if re.match(r'^RIC', codice, re.IGNORECASE) or re.match(r'COCA', codice, re.IGNORECASE) \
    or re.search(r'ATTIVAZIONE', descrizione,  re.IGNORECASE) or re.search(r"CARTA SERVIZI", descrizione, re.IGNORECASE): 
        return "RICARICHE" 
    
    if re.search(r'[A-Za-z]', codice) or re.search(r'WEARABLE', descrizione) or re.match(r'^30\d+$', codice) : 
        return "ACCESSORI"
    
    return "SCONOSCIUTO"

def trova_colonne_rim(df):
    nomi_colonne = []
    for col in df.columns:
        if not "U.A." in col:
            if "RIM" in col.upper():
                nomi_colonne.append(col)
    return nomi_colonne

def rimuovi_rim(lista_colonne):
    col_corrette = []
    for col in lista_colonne:
        try:
            parti = col.split(". ")
            nuovo_nome = parti[-1] if len(parti) > 1 else col
            col_corrette.append(nuovo_nome)
        except:
            col_corrette.appemd(col)

    return col_corrette

from io import StringIO
import pandas as pd

def prendi_dopo_vuoto(path_file):
    with open(path_file, encoding="latin-1") as f:
        righe = f.readlines()

    for i, riga in enumerate(righe):
        if riga.strip() == "" or set(riga.strip()) <= {";"}:
            idx_split = i
            break
    else:
        raise ValueError("Nessuna riga vuota trovata")

    righe_sotto = righe[idx_split + 1:]

    # 👉 FIX fondamentale
    testo = "".join(righe_sotto)

    df = pd.read_csv(
        StringIO(testo),
        sep=";",
        encoding="latin-1"
    )

    # pulizia colonne
    df.columns = df.columns.str.strip()

    print(df.head())

    return df

def main(path_file):
    
    # 1. importa il file, saltando le righe di intestazione e con encoding latin-1
    df = prendi_dopo_vuoto(path_file)
    
    # 2. trova il nome delle colonne dei negozi
    colonne_num = trova_colonne_rim(df)

    # 3. crea il subset
    subset_magazzino = df.loc[:445, ["Cod.Art.", "Nome Art."] + colonne_num]

    # 4. formatta il valore della pedonalità in int
    for col in colonne_num:
        subset_magazzino[col] = pd.to_numeric(subset_magazzino[col], errors = "coerce").fillna(0).astype(int)
    
    # 5.pulisce la lista dei nomi delle colonne 
    colonne_rinominate = rimuovi_rim(subset_magazzino.columns.tolist())

    # 6. riassegnare il nome alle colonne 
    subset_magazzino.columns = colonne_rinominate

    # 7. facendo unipivot per preparare il dataset all'analisi
    df_unpivot = subset_magazzino.melt(
        id_vars=["Cod.Art.", "Nome Art."],   # Colonne che restano fisse
        var_name="Magazzino",                # Nome della nuova colonna con i titoli (FID, PC2...)
        value_name="Quantità"                # Nome della nuova colonna con i numeri
    )

    # 8. inserimento colonna "CATEGORIA"
    df_unpivot.insert(
        2,                # posizione — inserisce prima di "Magazzino"
        "Categoria",      # nome della nuova colonna
        df_unpivot.apply(
            lambda riga: categorizza(riga["Cod.Art."], riga["Nome Art."]),
            axis=1
        )
    )

    df_magazzino = df_unpivot[df_unpivot["Quantità"] != 0]

    df_magazzino["Cod.Art."] = df_magazzino["Cod.Art."].astype(str)
    
    try:
        # 9. elimina file prima del salvataggio
        elimina_file_teams(PATH_TEAMS)

        # 10. salva su excel il file formattato in formato .parquet e .xlsx su teams
        salva_su_teams(PATH_TEAMS,df_magazzino)
        
    except Exception as e:
        print(f"Errore durante il salvataggio su Teams: {e}")

    finally:
        # 11. elimina il file RAW
        elimina_file_RAW(path_file)
        
if __name__ == "__main__":
    path_file = trova_file(PATH_RAW_FOLDER)
    prendi_dopo_vuoto(path_file)
    main(path_file)
    