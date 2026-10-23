import pandas as pd 
from config import trova_file, PATH_DB
from filtra_mes_set import lavora_df


def ordina_df(df):

    df = df.sort_values(by = ["Anno", "Data"], ascending = False)

    # esporta anno e settimana
    ultimo_giorno = df["Data"].iloc[0].date()  # prendi la prima, non la seconda
    ultimo_anno = ultimo_giorno.year
    ultima_settimana = (ultimo_giorno.isocalendar().week)

    return raggruppa_sett_negoz(df,ultimo_anno, ultima_settimana)

def raggruppa_sett_negoz(df, ultimo_anno, ultima_settimana):

    subset = df.groupby(["Negozio", "Settimana", "Anno"])["Presenze"].sum().reset_index()

    return subset, ultimo_anno, ultima_settimana


def calcola_w(anno, settimana):

    conta = 0
    lista_coppie = []
    while conta < 8:
        settimana -= 1
        
        if settimana <= 0:
            anno -= 1
            settimana = 52 
       
        lista_coppie.append((anno, settimana))
        conta += 1

    return lista_coppie


def main(path_db):

    # 1. importa df
    df = pd.read_parquet(path_db)
    
    # 2. aggiungi colonne mese e settimana
    df_lavorato = lavora_df(df)

    # 4. raggruppa per settimana e per negozio 
    df_ordinato, ultimo_anno, ultima_settimana = ordina_df(df_lavorato) 
    
    print(df_ordinato)
    # 5. selezione w - 8
    lista_sett = calcola_w(ultimo_anno, ultima_settimana)

    for anno, sett in lista_sett:
        print(df_ordinato[(df_ordinato["Settimana"] == sett) & (df_ordinato["Anno"] == anno)])


if __name__ == "__main__":
    path_db = trova_file(PATH_DB)
    main(path_db)
