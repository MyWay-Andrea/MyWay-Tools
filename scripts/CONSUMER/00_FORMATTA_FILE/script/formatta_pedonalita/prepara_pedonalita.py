import pandas as pd
from pathlib import Path

from formatta_pedonalita.config import NEGOZIO_CONDITION, COLONNE_ORDINATE, trova_file, PATH_RAW_FOLDER


#AGGIUNGI NEGOZIO N BASE AL CODICE
#-------------------------------------------------------------------------
def aggiungi_negozio(df):
    df["Cod.Dealer"] = df["Cod.Dealer"].astype(str).str.strip()
    df["Negozio"] = df["Cod.Dealer"].map(NEGOZIO_CONDITION)
    subset = df[df["Negozio"].notna()]

    return subset

#AGGIUNGI COLONNA DATA E ORA E PREPARA PER AGGIUNTA FASCIA ORARIA
#-------------------------------------------------------------------------
def prepara_data_ora(df):
    df[["inizio", "fine"]] = df["Data/Ora"].str.split(" - ", expand = True)
    df["inizio"] = pd.to_datetime(df["inizio"], format="%d-%m-%Y %H:%M:%S")

    df["Data"] = df["inizio"].dt.date
    df["Ora"] = df["inizio"].dt.time

    return df

#FUNZIONE DA RICHIAMARE IN AGGIUNGI_FASCIA:ORARIA (CONTEINE LE CONDIZIONI)
#-------------------------------------------------------------------------
def assegna_fascia(ora):
    if ora < 9:
        return "A Notte-Mattina"
    elif ora < 11:
        return  "B 09:00-11:00"
    elif ora < 13:
        return  "C 11:00-13:00"
    elif ora < 14:
            return  "D Pausa Pranzo"
    elif ora < 16:
            return  "E 14:00-16:00"
    elif ora < 19:
            return  "F 16:00-19:00"
    elif ora >= 19:
         return "G Sera-Notte"


#AGGIUNGE LA COLONNA FASCIA ORARIA    
#-------------------------------------------------------------------------
def aggiugni_fascia_oraria(df):
    #dato che e object/string, la converto in data per poi in ora(intero)
    df["Ora"] = pd.to_datetime(df["Ora"], format = "%H:%M:%S").dt.hour
    df["Fascia oraria"] = df["Ora"].apply(assegna_fascia)

    return df

#AGGIUNGE COLONNA CON GIORNO DELLA SETTIMANA
#-------------------------------------------------------------------------
def aggiungi_giorno(df):
    df["Data"] = pd.to_datetime(df["Data"], format = "%d-%m-%Y")
    #df["Giorno"] = df["Data"].dt.day_name(locale='it_IT')
    mappa_giorni = {
        0: "Lunedì",
        1: "Martedì", 
        2: "Mercoledì",
        3: "Giovedì",
        4: "Venerdì",
        5: "Sabato",
        6: "Domenica"
    }

    df["Giorno_num"]  = df["Data"].dt.dayofweek         
    df["Giorno"] = df["Giorno_num"].map(mappa_giorni)  
    return df

#FILTRA IL DF PRINCIPALE PER CREARE UN SUBSET CON LE COLONNE GIUSTE
#-------------------------------------------------------------------------
def seleziona_colonne(df, colonne):
     subset = df[colonne].copy()

     return subset

#FLUSSO PRINCIPALE
#-------------------------------------------------------------------------
def main(ped_raw):

    #leggi file 
    df = pd.read_excel(ped_raw)

    subset = aggiungi_negozio(df)
    subset = prepara_data_ora(subset)
    subset = aggiugni_fascia_oraria(subset)
    subset = aggiungi_giorno(subset)
    subset_filtrato = seleziona_colonne(subset, COLONNE_ORDINATE)

    return subset_filtrato