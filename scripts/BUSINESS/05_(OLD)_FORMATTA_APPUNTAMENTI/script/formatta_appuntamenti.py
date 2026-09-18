import pandas as pd
from pathlib import Path
from openpyxl import load_workbook

from config import filtro_appuntamento, COLONNA_DATA as COL_DATA, COLONNA_AGENTE_APP, \
    copia_template, copia_formattaz_cella, MASTER_APPUNTAMENTI as MASTER, \
        SHEET_APPUNTAMENTI, trova_raw_file, PATH_RAW_FILE, svuota_cartella, \
        copia_su_teams, PERCORSO_TEAMS

from colorama import Fore, Style, init
init(autoreset=True) # Resetta il colore automaticamente dopo ogni print

#FILTRA LA CONOLLA "TIPO APPUNTAMENTO"
#-----------------------------------------------------------
def filtra_df(df):
    if not df.empty:
        colonna = df.columns[10]
        
        # Filtro tipo appuntamento
        df_filtrato = df[df[colonna].isin(filtro_appuntamento)].copy()
        
        # Pulizia colonna azienda
        df_filtrato.loc[:, ' "Relativi a"'] = df_filtrato.loc[:, ' "Relativi a"'].str.replace("Accounts::::", "", regex=False)

        # Rinomina colonna agente
        df_filtrato = df_filtrato.rename(columns={df_filtrato.columns[3]: COLONNA_AGENTE_APP})
        
        # 1. Conversione a datetime (Fondamentale per i calcoli)
        df_filtrato[COL_DATA] = pd.to_datetime(df_filtrato[COL_DATA], dayfirst=True)
        
        # 2. Filtra per data (FALLO QUI, mentre è un oggetto datetime)
        # Usiamo il formato ISO 'YYYY-MM-DD' per il confronto sicuro
        df_filtrato = df_filtrato[df_filtrato[COL_DATA] >= "2026-01-01"].copy()

        return df_filtrato
    
    print("Il dataframe è vuoto...")
    return df


#RIMUVOI REGIONI SOCIALI VUOTE
#-----------------------------------------------------------
def rimuovi_regioni_vuote(df):
    if not df.empty:
        colonna = df.columns[0]
        df_filtrato = df[df[colonna].notna()]

        return df_filtrato
    
    return df, print("Il dataframe è vuoto...")

#FORZA FORMATO COLONNE FILE EXCEL
#----------------------------------------------------
def forza_formato_excel(ws):
    for row in range(2, ws.max_row + 1):
        #FORZA COLONNA DATE
        ws.cell(row = row, column = 2).number_format = 'DD/MM/YYYY'




#POPOLA IL TEMPLATE CON I DATI PULITI
#----------------------------------------------------
def popola_template(file_appuntamenti, df, sheet):
    
    wb = load_workbook(file_appuntamenti)
    ws = wb[sheet]

    #copia formato delle celle della riga "2" e lo copia prima di incollare il valore
    template_stili = {idx_col: ws.cell(row=2, column=idx_col) 
                    for idx_col in range(1, len(df.columns) +2 )}
    
    for idx_riga, row_data in enumerate(df.values, start=2):
        for idx_col, valore in enumerate(row_data, start=1):
            cella_destinazione = ws.cell(row=idx_riga, column=idx_col)
            copia_formattaz_cella(template_stili[idx_col], cella_destinazione)
            cella_destinazione.value = valore

    forza_formato_excel(ws)

    wb.save(file_appuntamenti)
    wb.close()

#APPLICA COLONNE CORRETTE PARQUET
#----------------------------------------------------------
colonne_parquet = ["Regione sociale", "Data appuntamento",
                    "Tipo appuntamento", "Azienda assegnata a ",
                    "Esito Appuntamento", "Note Appuntamento"]

colonne_da_filtrare = [6, 2, 10, 1, 27, 28]

def filtra_e_applica_colonne_corrette(df, colonne, colonne_da_filtrare):
    subset = df.iloc[:, colonne_da_filtrare].copy()
    subset.columns = colonne
    return subset

#FUNZIONE PRINCIPALE 
#-----------------------------------------------------------
def main(file_app_raw):
    df = pd.read_csv(file_app_raw, 
                    low_memory=False)
    
    df = filtra_df(df)
    nome = "Appuntamenti.xlsx"
    file_app_finale = copia_template(MASTER, nome = nome)
    
    subset = filtra_e_applica_colonne_corrette(df, colonne_parquet, colonne_da_filtrare)
    popola_template(file_app_finale, subset, SHEET_APPUNTAMENTI)
    
    #salva su teams il file 'Opportunità.xlsx'
    copia_su_teams(file_app_finale, PERCORSO_TEAMS)

    #salva su temas il file in formato '.parquet'
    copia_su_teams(subset)

    #svuota cartella dal file appena analizzato/formattato
    svuota_cartella(PATH_RAW_FILE, "Appuntameent")

    print(Fore.GREEN + "\n ✔ FORMATTAZIONE APPUNTAMENTI ESEGUITA CON SUCCESSO")
    
    


if __name__ == "__main__":
    file_appuntamenti_raw = trova_raw_file(PATH_RAW_FILE)
    main(file_appuntamenti_raw)