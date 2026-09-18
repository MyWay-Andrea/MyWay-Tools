#IMPORT LIBRERIE
#--------------------------------------------------------
import pandas as pd
from copy import copy 
from pathlib import Path
import shutil
from datetime import date, datetime
from openpyxl import load_workbook

#PRE PRINT COLORATI
from colorama import Fore, Style, init
init(autoreset=True) # Resetta il colore automaticamente dopo ogni print

#IMPORTA FILE DI SUPPORTO
#-------------------------------------------------------
from OneDrive import copia_in_onedrive 

# IMPORTAZIONE VARIABILI GLOBALI
#--------------------------------------------------------
from config import (COL_NOMI, COLONNA_AGENTE_GARA, COLONNA_AGENTE_APP, LISTA_NOMI as LISTA_NOMI_GARA,
                            FILE_MASTER_VENDITORI as FILE_MASTER, COL_DATA_ATTIVAZIONE, COL_DATA_INSERIMENTO, ONEDRIVE_VENDITORI as PERCORSI_VENDITORI)


#LEGGERE AGENTI DA FILE LISTA NOMI
#-------------------------------------------------------
def leggi_agenti_gara(lista_nomi):
    df = pd.read_excel(lista_nomi, sheet_name="nomi", header=None)

    return df[COL_NOMI]

#COPIA FORMATTAZIONE CELLE 
#--------------------------------------------------------
def copia_formattaz_cella(cella_input, cella_output):
    if cella_input.has_style:
        cella_output.font = copy(cella_input.font)
        cella_output.border = copy(cella_input.border)
        cella_output.fill = copy(cella_input.fill)
        cella_output.number_format = copy(cella_input.number_format)
        cella_output.protection = copy(cella_input.protection)
        cella_output.alignment = copy(cella_input.alignment)

#COPIA TEMPLATE
#--------------------------------------------------------
def copia_template(file_master, agente, cartella_output):
    cartella_output = Path(cartella_output)
    cartella_output.mkdir(parents=True, exist_ok=True)

    file_output = cartella_output / f"FCST_{agente}.xlsx"
    shutil.copy(file_master, file_output)

    return file_output

#POPOLA FOGLIO FCST
#--------------------------------------------------------
def popola_foglio_fcst(wb, df_da_inserire, df_in_attivazione, df_attive):
    ws_fcst = wb["FCST"]
    #cerca la prima colonna "Agente" nei 3 df e la salva nella variabile
    agente = next((df[COLONNA_AGENTE_GARA].iloc[0] 
                    for df in [df_da_inserire, df_in_attivazione, df_attive] 
                    if not df.empty), None)
    
    oggi = date.today()
    data_oggi = oggi.strftime("%d/%m/%Y")

    ws_fcst.cell(row=9, column=2).value = agente
    ws_fcst.cell(row=2,column=2).value = data_oggi

#SCRIVI DATI NEI FOGLI
#--------------------------------------------------------
def scrivi_dati_nei_fogli(file_venditore, df_filtrato, agente_opp, df_opp_completo, df_app_completo):
    
    inserimento_vuoto = (df_filtrato[COL_DATA_INSERIMENTO].isna()) | (df_filtrato[COL_DATA_INSERIMENTO].astype(str).str.strip() == "")
    attivazione_vuota = (df_filtrato[COL_DATA_ATTIVAZIONE].isna()) | (df_filtrato[COL_DATA_ATTIVAZIONE].astype(str).str.strip() == "")

    df_da_inserire    = df_filtrato[inserimento_vuoto & attivazione_vuota]
    df_in_attivazione = df_filtrato[(~inserimento_vuoto) & attivazione_vuota]
    df_attive         = df_filtrato[(~inserimento_vuoto) & (~attivazione_vuota)]

    wb = load_workbook(file_venditore)

    # FOGLI GARA
    fogli = [
        ("DA INSERIRE", df_da_inserire),
        ("IN ATTIVAZIONE", df_in_attivazione),
        ("ATTIVE", df_attive)
    ]
    for nome_foglio, df in fogli:
        if df.empty:
            continue
        
        ws = wb[nome_foglio]
         
        template_stili = {idx_col: ws.cell(row=2, column=idx_col) 
                          for idx_col in range(2, len(df.columns) + 2)}
        
        for idx_riga, row_data in enumerate(df.values, start=2):
            for idx_col, valore in enumerate(row_data, start=2):
                cella_destinazione = ws.cell(row=idx_riga, column=idx_col)
                copia_formattaz_cella(template_stili[idx_col], cella_destinazione)
                cella_destinazione.value = valore

    # FOGLIO OPPORTUNITA
    ws_opp = wb["OPPORTUNITA"]

    righe_opp = df_opp_completo.iloc[:,2].str.contains(agente_opp, case=False, na=False, regex=False)
    df_opp = df_opp_completo[righe_opp].copy()

    if df_opp.empty:
        print(Fore.RED + f"  ⚠️  Nessuna opportunità aperta per {agente_opp}")
    else:
        template_stili_opp = {idx_col: ws_opp.cell(row=2, column=idx_col)
                               for idx_col in range(1, len(df_opp.columns) + 1)}

        for idx_riga, row_data in enumerate(df_opp.values, start=2):
            for idx_col, valore in enumerate(row_data, start=1):
                cella_destinazione = ws_opp.cell(row=idx_riga, column=idx_col)
                copia_formattaz_cella(template_stili_opp[idx_col], cella_destinazione)
                cella_destinazione.value = valore

    # FOGLIO APPUNTAMENTI
    ws_app = wb["APPUNTAMENTI"]

    righe_app = df_app_completo[COLONNA_AGENTE_APP].str.contains(agente_opp, case=False, na=False, regex=False)
    df_app = df_app_completo[righe_app].copy()

    if df_app.empty:
       print(Fore.RED + f"  ⚠️  Nessun appuntamento trovato per {agente_opp}")
    else:
        template_stili_app = {idx_col: ws_app.cell(row=2, column=idx_col)
                                for idx_col in range(2, len(df_app.columns) + 2)}

        for idx_riga, row_data in enumerate(df_app.values, start=2):
            for idx_col, valore in enumerate(row_data, start=2):
                cella_destinazione = ws_app.cell(row=idx_riga, column=idx_col)
                copia_formattaz_cella(template_stili_app[idx_col], cella_destinazione)
                cella_destinazione.value = valore
                if isinstance(valore, (datetime, pd.Timestamp)):
                    cella_destinazione.number_format = 'dd/MM/yyyy'

    # FOGLIO FCST
    popola_foglio_fcst(wb, df_da_inserire, df_in_attivazione, df_attive)

    #SALVA FILE IN ONEDRIVE

    wb.save(file_venditore)
    wb.close()

# FUNZIONE MAIN
# I file sono già puliti — legge direttamente senza prepara_*
#--------------------------------------------------------
def main(df_gara_completo, cartella_output, df_opp_completo, df_app_completo): 

    #agenti_gara = leggi_agenti_gara(LISTA_NOMI_GARA)
    agenti_gara = pd.unique(
        pd.concat([
            df_gara_completo[COLONNA_AGENTE_GARA], 
            df_app_completo[COLONNA_AGENTE_APP]
        ])
    )
    
    for agente in agenti_gara:
        
        print(f"\n{agente}\n")
        righe = df_gara_completo[COLONNA_AGENTE_GARA].str.contains(agente, case=False, na=False, regex=False)
        df_agente = df_gara_completo[righe].copy()

        if df_agente.empty:
            print(Fore.RED + f"  ⚠️  Nessun dato trovato per {agente} nel file GARA ⚠️")
            continue

        file_agente = copia_template(FILE_MASTER, agente, cartella_output)
        scrivi_dati_nei_fogli(file_agente, df_agente, agente, df_opp_completo, df_app_completo)

        try:
            #percorso = PERCORSI_VENDITORI[agente] / file_agente.name
            #elimina_file_da_cartella(percorso)
            copia_in_onedrive(file_agente, PERCORSI_VENDITORI, agente)
            print(Fore.GREEN + "  ✅ salvato su TEAMS")
        except Exception as e:
            print(Fore.RED + f"  ❌ Agente: {agente} non trovato, vado avanti\n")
            continue 

    print(f"\nSono stati creati {len(agenti_gara)} file per i venditori nella cartella: {cartella_output}")
    print("\nElaborazione completata! 🎉")