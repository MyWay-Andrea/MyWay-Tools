import pandas as pd
from pathlib import Path
from colorama import Fore, init, Style
init(autoreset=True)
import datetime
import calendar
import shutil
from openpyxl import load_workbook

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

#temporaneo da togliere l'ardcodede e renderlo dinamico
TEMPLATE_PATH = PATH_DIR / "SCRIPT" / "CONSUMER" / "06_AGGREGA_INCENTIVI_GARA" / "TEMPLATE" / "TEMPLATE_PREMIO.xlsx"
def trova_file_da_teams(dict_path: dict, parametro:str) -> list:
    files = []
    if isinstance(dict_path, dict):
        for negozio, path in dict_path.items():
            print(f"\nlettura: {negozio}...")
            if path.is_dir():
                files_cartella = path.glob(parametro)
                for file in files_cartella:
                    print("File trovato: " + Fore.LIGHTBLUE_EX + f"{file.name}")
                    files.append(file)

    return files

def crea_lista_df(files):
    print("\n")
    lista_df = []
    for file in files:
        try:
            #estrae nome
            nome_negozio = file.name.split("_")[1].upper()
            print(f"Lettura in corso:" + Fore.CYAN+ f"{nome_negozio}...")
            df = pd.read_excel(file, usecols="C:H", skiprows=4, nrows=10, na_values=["", " ", "-"], keep_default_na=True)
            #rimuove righe vuote (dove non c'è la data)
            df = df.dropna(subset=['Store Spec'])
            df = df[df['Store Spec'] != 'Totale']
            
            lista_df.append(df)

        except Exception as e:
            print(Fore.RED + f"Errore su {file.name}: {e}")

    return lista_df

def aggrega_df(lista_df):
    if lista_df:
        try:

            df_aggregato = pd.concat(lista_df, ignore_index = True)
        
            colonne_numeriche = [
                "Voce/Dati",
                "Fissa",
                "Energia",
                "Solution",
                "Easy Rent"
            ]
            #assicura che le colonne siano numeriche per la Group By
            df_aggregato[colonne_numeriche] = (df_aggregato[colonne_numeriche].apply(pd.to_numeric,errors="coerce"))

            #raggruppa i valori per i venditori presenti su più puni vendita
            df_aggregato = df_aggregato.groupby("Store Spec", as_index = False)[colonne_numeriche].sum(min_count=1)
            
            print(f"\n{Fore.GREEN}Successo!{Style.RESET_ALL} Aggregati {len(lista_df)} file.")
            print(f"Totale righe: {len(df_aggregato)}")
            
        except Exception as e:
            print(Fore.RED + f"errore: {e}")

        print(f"df_aggregato:\n\n{df_aggregato}")
    return df_aggregato

def popola_template_da_df(df, path_template, path_output, nome_output):
    
    # 1. Copia il template
    filename = path_output / nome_output
    shutil.copy2(path_template, filename)
    
    # 2. Carica il file con openpyxl
    wb = load_workbook(filename)
    ws = wb.active 

    # 3. Gestione Data/Giorni
    oggi = datetime.datetime.now()
    _, giorni_totali = calendar.monthrange(oggi.year, oggi.month)
    ws['D2'] = oggi.day
    ws['E2'] = giorni_totali

    # 4. Costruisci un dizionario {nome_venditore: numero_riga} leggendo la colonna 3 del template
    riga_inizio = 6
    riga_fine = ws.max_row  # oppure metti un numero fisso es: 30

    nomi_template = {}
    for riga in range(riga_inizio, riga_fine + 1):
        valore_cella = ws.cell(row=riga, column=3).value
        if valore_cella is not None:
            nomi_template[str(valore_cella).strip().upper()] = riga

    # 5. Scrivi i dati solo dove il nome corrisponde
    for _, riga_df in df.iterrows():
        nome_venditore = str(riga_df['Store Spec']).strip().upper()
        
        if nome_venditore in nomi_template:
            riga_corrente = nomi_template[nome_venditore]
            
            ws.cell(row=riga_corrente, column=4).value = "" if pd.isna(riga_df['Voce/Dati'])  else riga_df['Voce/Dati']
            ws.cell(row=riga_corrente, column=5).value = "" if pd.isna(riga_df['Fissa'])      else riga_df['Fissa']
            ws.cell(row=riga_corrente, column=6).value = "" if pd.isna(riga_df['Energia'])    else riga_df['Energia']
            ws.cell(row=riga_corrente, column=7).value = "" if pd.isna(riga_df['Solution'])   else riga_df['Solution']
            ws.cell(row=riga_corrente, column=8).value = "" if pd.isna(riga_df['Easy Rent'])  else riga_df['Easy Rent']
        else:
            print(f"\n⚠️ Store '{riga_df['Store Spec']}' non trovato nel template, riga saltata.")

    # 6. Salva
    wb.save(filename)
    print(f"\n✅ File salvato: {filename}")
