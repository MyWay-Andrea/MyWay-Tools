from config import trova_raw_file, PATH_PARQUET, SETTIMANA_CORRENTE, DATA_FILTRO, COLONNE_APPUNTAMENTI

import pandas as pd 

def filtra_df(df):

    
    df["Data appuntamento"] = pd.to_datetime(df["Data appuntamento"], format="%d/%m/%Y")
    subset = df[df["Data appuntamento"] >= DATA_FILTRO]

    return subset

def aggiungi_settimana(df):

    
    df["SETTIMANA"] = df['Data appuntamento'].dt.isocalendar().week


    return df

def filtra_corrente(df):

    subset = df[df["SETTIMANA"] == SETTIMANA_CORRENTE]
    return subset

def main(path):

    df = pd.read_parquet(path)

    #1. filtra df 2026
    df_filtrato = filtra_df(df)
    
    #2. aggiungi colonna settimana
    subset = aggiungi_settimana(df_filtrato)

    #3. filtra solo sett corrente
    subset_corrente = filtra_corrente(subset)
    #4. riordina colonna per entrambi i df
    subset = subset[COLONNE_APPUNTAMENTI] 
    subset_corrente = subset_corrente[COLONNE_APPUNTAMENTI]

    #RESTITUISCE I DUE DF PER I DUE FOGLI
    return subset, subset_corrente


if __name__ == "__main__":
    path_appuntamenti = trova_raw_file(PATH_PARQUET)
    main(path_appuntamenti)