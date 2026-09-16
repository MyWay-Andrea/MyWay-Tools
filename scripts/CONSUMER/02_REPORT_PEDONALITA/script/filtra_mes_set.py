
import pandas as pd

def filtra_df(df, filtro=None):

    if filtro is None:
        print("\nNon hai inserito la condizione del filtro. ESCO...\n")
        exit()

    df = df.sort_values("Data")

    ultimo_giorno = df["Data"].iloc[-1]
    ultimo_mese = ultimo_giorno.month
    ultimo_anno = ultimo_giorno.year
    ultima_settimana = ultimo_giorno.isocalendar().week

    if filtro.lower() == "mese":
        df = df[(df["Mese"] == ultimo_mese) &
                (df["Anno"] == ultimo_anno)]

    elif filtro.lower() == "settimana":
        df = df[(df["Anno"] == ultimo_anno) &
                (df["Settimana"] == ultima_settimana)]

    return df

def lavora_df(df, filtro=None):

    col_data = next((c for c in df.columns if "Data" in c), None)
    
    if col_data is None:
        raise ValueError("Nessuna colonna contenente 'Data' trovata")

    df[col_data] = pd.to_datetime(df[col_data], dayfirst=True, errors="coerce")
    
    df = df.dropna(subset=[col_data])  # 🔥 importante

    df["Anno"] = df[col_data].dt.year
    df["Mese"] = df[col_data].dt.month
    df["Settimana"] = df[col_data].dt.isocalendar().week.astype(int)
    print(df[col_data].max())
    print(df[col_data].max().isocalendar())

    return filtra_df(df, filtro) if filtro else df