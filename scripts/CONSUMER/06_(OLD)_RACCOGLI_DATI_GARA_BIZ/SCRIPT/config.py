import pandas as pd
from pathlib import Path
from colorama import Fore, init, Style
init(autoreset=True)
import datetime
import calendar
import shutil
from openpyxl import load_workbook
import sys

PATH_HOME = Path.home()
PATH_DIR = Path(__file__).parents[4]
ONEDRIVE_PATH = {
    "TORRI" : PATH_HOME / "My Way S.r.l" / "TEAM - TORRI - TEAM - TORRI" / "TRACCIAMENTO",
    "CARPI": PATH_HOME / "My Way S.r.l" / "TEAM - CARPI - TEAM - CARPI" / "TRACCIAMENTO",
    "EUROSIA" : PATH_HOME / "My Way S.r.l" / "TEAM - EUROSIA - TEAM - EUROSIA" / "TRACCIAMENTO",
    "FIDENZA" : PATH_HOME / "My Way S.r.l" / "TEAM - FIDENZA - TEAM - FIDENZA" / "TRACCIAMENTO",
    "GALASSIA" : PATH_HOME / "My Way S.r.l" / "TEAM - GALASSIA - TEAM - GALASSIA" / "TRACCIAMENTO",
    "PIACENZA MEDIAWORLD"   :PATH_HOME / "My Way S.r.l" / "TEAM - PIACENZA MED - TEAM - PIACENZA MED" / "TRACCIAMENTO",
    "SASSUOLO" : PATH_HOME / "My Way S.r.l" / "TEAM - SASSUOLO - TEAM - SASSUOLO" / "TRACCIAMENTO",
}



#temporaneo per prova
OUTPUT_PATH = PATH_HOME / "My Way S.r.l" / "TEAM CONSUMER - TEAM CONSUMER"


TEMPLATE_PATH = PATH_DIR / "SCRIPT" / "CONSUMER" / "06_RACCOGLI_DATI_GARA_BIZ" / "TEMPLATE" / "TEMPLATE_PREMIO.xlsx"

COLONNE_ORDINATE = ["VENDITORE", "DATA ATTIVAZIONE", "CATEGORIA", "Qtà"]


def trova_file_da_teams(dict_path: dict, parametro:str) -> list:
    files = []
    if isinstance(dict_path, dict):
        for negozio, path in dict_path.items():
            if path.is_dir():
                files_cartella = list(path.glob(parametro))

                if not files_cartella:
                    print(f"{negozio}" + Fore.LIGHTRED_EX +" X")

                for file in files_cartella:
                    print(f"{negozio} - {file.name}" + Fore.LIGHTGREEN_EX +" ✓")
                    files.append(file)

    return files

def crea_lista_df(files):
    lista_df = []
    for file in files:
        try:
            df = pd.read_excel(file) 

            lista_df.append(df)

        except Exception as e:
            print(Fore.RED + f"Errore su {file.name}: {e}")

    return lista_df

def _elabora_df(df):
    # assegnazione formato variabile 
    df["Qtà"] = pd.to_numeric(df["Qtà"], errors="coerce")
    df["DATA ATTIVAZIONE"] = pd.to_datetime(df["DATA ATTIVAZIONE"], errors="coerce", dayfirst=True)
    
    # temporaneo il fillna(12/05/2026)
    df["DATA ATTIVAZIONE"] = df["DATA ATTIVAZIONE"].fillna(pd.Timestamp("2026-05-12"))
    
    # filtra solo i contratti attivati questo mese
    oggi = pd.Timestamp.today()
    df_attivi = df[
        (df["DATA ATTIVAZIONE"].dt.month == oggi.month) &
        (df["DATA ATTIVAZIONE"].dt.year == oggi.year)
    ].copy()
    #controllo per non far scrashare senon ci sono contratti
    if len(df_attivi) == 0:
        print(Fore.RED + "\nNON CI SONO CONTRATTI CHIUSI PER QUESTO MESE.\n" + Fore.RESET + "esco 👋")
        sys.exit(1)

    # rinomina categorie togliendo il suffisso _BIZ 
    df_attivi["CATEGORIA"] = [valore.split("_")[0] if "_" in str(valore) else valore for valore in df_attivi["CATEGORIA"]]
    
    # Rinomina venditori rimuovendo il cognome 
    df_attivi["VENDITORE"] = [valore.split(" ")[0] if " " in str(valore) else valore for valore in df_attivi["VENDITORE"]]

    # normalizza a titolo per confronti uniformi  ← fillna + astype per gestire NaN
    df_attivi["CATEGORIA"] = df_attivi["CATEGORIA"].fillna("").astype(str).str.strip().str.title()
    df_attivi["SERVIZIO"]  = df_attivi["SERVIZIO"].fillna("").astype(str).str.strip().str.title()

    # promuovi Energia ed Easy Rent da SERVIZIO a CATEGORIA
    SERVIZI_DA_PROMUOVERE = ["Energy", "Easy Rent"]
    mask = df_attivi["SERVIZIO"].isin(SERVIZI_DA_PROMUOVERE)
    df_attivi.loc[mask, "CATEGORIA"] = df_attivi.loc[mask, "SERVIZIO"] 

    # unisci Voce e Dati
    RINOMINA = {"Voce": "Voce/Dati", "Dati": "Voce/Dati"}
    df_attivi["CATEGORIA"] = df_attivi["CATEGORIA"].replace(RINOMINA)

    # rimuovi righe con VENDITORE non valido
    df_attivi["VENDITORE"] = df_attivi["VENDITORE"].fillna("").astype(str).str.strip()
    df_attivi = df_attivi[df_attivi["VENDITORE"].str.lower() != "nan"]
    df_attivi = df_attivi[df_attivi["VENDITORE"] != ""]
    
    return df_attivi

def aggrega_df(lista_df, colonne_ordinate):
    '''
    Aggrega tutti i df della lista, riorganizza le colonen utilizzando solo quelle necessarie
    e elimina le righe vuote in "DATA ATTIVAZIONE" in modo da elaborare più avanti soltanto 
    i reord inseriti del mese corrente 
    '''
    if not lista_df:
        print(Fore.RED + "Nessun file da aggregare.")
        return None
    
    try:

        df_aggregato = pd.concat(lista_df, ignore_index = True)
        print(f"\n{Fore.GREEN}Successo!{Style.RESET_ALL} Aggregati {len(lista_df)} file.")
        print(f"Totale righe: {len(df_aggregato)}")
        
        
        df_elaborato = _elabora_df(df_aggregato)
        print(df_elaborato)
        #riorganizza le colonne e se non esiste mette Nan
        df_organizzato = df_elaborato.reindex(columns = colonne_ordinate)
        print(df_organizzato)

        return df_organizzato

    except Exception as e:
        print(Fore.RED + f"errore: {e}")

    


def create_dict_sales(df):
    '''
    Prende il df_elaborato e restituisce un dict con:
    - chiave: nome venditore in UPPER
    - valore: df filtrato per venditore, con categorie raggruppate
    '''
    if df is None or df.empty:
        print(Fore.RED + " ❌ Errore --> il programma s è interrotto perchè nella creazione\ndel dizionario il df è vuoto")
        sys.exit(1)

    ORDINE_CATEGORIE = ["Voce/Dati", "Fissa", "Energia", "Solution", "Easy Rent"]

    # pivot: una riga per venditore, una colonna per categoria
    df_pivot = df.pivot_table(
        index="VENDITORE",
        columns="CATEGORIA",
        values="Qtà",
        aggfunc="sum",
        fill_value=0        # dove non c'è nulla mette 0 invece di NaN
    ).reset_index()

    # rimuove il nome dell'asse colonne (artefatto di pivot_table)
    df_pivot.columns.name = None

    # aggiunge le colonne mancanti con 0 e ordina
    for cat in ORDINE_CATEGORIE:
        if cat not in df_pivot.columns:
            df_pivot[cat] = 0

    colonne_finali = ["VENDITORE"] + ORDINE_CATEGORIE
    df_pivot = df_pivot[colonne_finali]

    # costruisce il dict: chiave VENDITORE in upper, valore la sua riga come df
    dict_sales = {}
    for _, row in df_pivot.iterrows():
        venditore = row["VENDITORE"].upper()
        dict_sales[venditore] = row.to_frame().T.reset_index(drop=True)

    return dict_sales

    
def popola_template_da_dict(dict_sales, path_template, path_output, nome_output):
    
    # 1. Copia il template
    filename = Path(path_output / nome_output)

    shutil.copy2(path_template, filename)
    
    # 2. Carica il file con openpyxl
    wb = load_workbook(filename)
    ws = wb.active 

    # 3. Gestione Data/Giorni
    oggi = datetime.datetime.now()
    _, giorni_totali = calendar.monthrange(oggi.year, oggi.month)
    ws['D2'] = oggi.day
    ws['E2'] = giorni_totali

    # 4. Costruisci un dizionario {nome_venditore: numero_riga} leggendo la colonna agente
    riga_inizio = 6
    riga_fine = ws.max_row
    nomi_template = {}
    for riga in range(riga_inizio, riga_fine + 1):
        valore_cella = ws.cell(row=riga, column=3).value
        if valore_cella is not None:
            nomi_template[str(valore_cella).strip().upper()] = riga

    # 5. Scrivi i dati solo dove il nome corrisponde
    for venditore, df_venditore in dict_sales.items():
        # venditore è già in UPPER dal create_dict_sales
        if venditore in nomi_template:
            riga_corrente = nomi_template[venditore]
            row = df_venditore.iloc[0]  # è una riga singola

            ws.cell(row=riga_corrente, column=4).value = 0 if pd.isna(row['Voce/Dati'])  else row['Voce/Dati']
            ws.cell(row=riga_corrente, column=5).value = 0 if pd.isna(row['Fissa'])       else row['Fissa']
            ws.cell(row=riga_corrente, column=6).value = 0 if pd.isna(row['Energia'])     else row['Energia']
            ws.cell(row=riga_corrente, column=7).value = 0 if pd.isna(row['Solution'])    else row['Solution']
            ws.cell(row=riga_corrente, column=8).value = 0 if pd.isna(row['Easy Rent'])   else row['Easy Rent']
        else:
            print(f"\n ⚠️ Venditore '{venditore}' non trovato nel template, riga saltata.")

    # 6. Salva
    wb.save(filename)
    print(f"\n✅ File salvato: {filename}")