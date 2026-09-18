import pandas as pd
import numpy as np
from openpyxl import load_workbook
import logging 

from config import COLONNE, SERVIZI_DA_SCONTARE, COLONNA_AGENTE_GARA, \
    MASTER_GARA as MASTER, SHEET_GARA, DATE_COLS_NAME as DATE_COLS, \
    copia_formattaz_cella, copia_template

from colorama import Fore, Style, init
init(autoreset=True) # Resetta il colore automaticamente dopo ogni print
           
#FORZA FORMATO COLONNE
#----------------------------------------------------
def forza_formato_dati(df):

    #formato importi
    df.iloc[:, 5:8] = df.iloc[:, 5:8].apply(pd.to_numeric, errors='coerce')

    #formato date
    for col in DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    df = df.rename(columns = {df.columns[12]: COLONNA_AGENTE_GARA})
    df[COLONNA_AGENTE_GARA] = df[COLONNA_AGENTE_GARA].astype(str).str.strip()
    
    return df

#FUNZIONE PER CALCOLARE IL PREZZO TOTALE CORRETTO
#----------------------------------------------------
def calcola_prezzo(df):
    try:
        df["Importo Calcolato"] = df.iloc[:, 7].copy()  

        for idx, servizio in df.iloc[:, 4].items():
            if servizio in SERVIZI_DA_SCONTARE:
                df.loc[idx, "Importo Calcolato"] = (
                    df.loc[idx, df.columns[7]]
                    - (df.loc[idx, df.columns[7]] * (df.loc[idx, df.columns[16]] / 100))
            )
        return df
    except Exception as e:
        logging.warning(f"  ⚠️ ATTENZIONE errore nel calcolo dell'importo calcolato nel file di gara. errore: {e} ")


#AGGIUNGI LE TRE COLONNE VUOTE
#----------------------------------------------------
def aggiungi_colonne_vuote(subset):
    #trova nome della colonna 16
    colonne = subset.columns.tolist()
    nome_colonna_16 = colonne[16]
    
    #rimuove e salva in una variabile la colonna 16
    scala_sconti = subset.pop(nome_colonna_16)
    
    #aggiuge le 3 colonne vuote e assegna all 19 i valori salvati nella variabile 
    subset[16] = np.nan
    subset[17] = np.nan
    subset[18] = np.nan
    subset[19] = scala_sconti
    
    return subset


#FORZA FORMATO COLONNE FILE EXCEL
#----------------------------------------------------
def forza_formato_excel(ws):
    for row in range(2, ws.max_row + 1):

        #FORZA COLONNA DATE
        ws.cell(row=row, column= 9).number_format = 'DD/MM/YYYY'
        ws.cell(row=row, column= 10).number_format = 'DD/MM/YYYY'
        ws.cell(row=row, column= 11).number_format = 'DD/MM/YYYY'
        ws.cell(row=row, column= 12).number_format = 'DD/MM/YYYY'

        #FORZA COLONNE VALUTA
        ws.cell(row=row, column= 7).number_format = '#,##0.00 €'
        ws.cell(row=row, column= 8).number_format = '#,##0.00 €'

#POPOLA IL TEMPLATE CON I DATI PULITI
#----------------------------------------------------
def popola_template(file_gara, df, sheet):
    wb = load_workbook(file_gara)

    ws = wb[sheet]

    #copia formato delle celle della riga "2" e lo copia prima di incollare il valore
    template_stili = {idx_col: ws.cell(row=2, column=idx_col) 
                          for idx_col in range(1, len(df.columns) +2 )}

    for idx_riga, row_data in enumerate(df.values, start=2):
        for idx_col, valore in enumerate(row_data, start=1):
            cella_destinazione = ws.cell(row=idx_riga, column=idx_col)
            copia_formattaz_cella(template_stili[idx_col], cella_destinazione)
            cella_destinazione.value = valore

    #forza formato colonne file gara finale
    forza_formato_excel(ws)

    #salva i dati        
    wb.save(file_gara)
    wb.close()

#APPLICA COLONNE CORRETTE
#---------------------------------------------------
COLONNE_CORRETTE = ['Cliente (Ordine)', 'Partita IVA (Ordine)', 'ID Pratica',
       'Prodotto esistente', 'Tipologia Servizio (Prodotto esistente)',
       'Quantità', 'Prezzo unitario', 'Importo totale', 'Data creazione',
       'Data Inserimento OmniSales', 'Data Passaggio ACA', 'Data Attivazione',
       'Proprietario (Ordine)', 'ID ordine (Ordine)', 'Motivo stato (Ordine)',
       'Valuta', 'Codice Aggregato', 'Famiglia', 'Squadra Energia',
       'scala sconti']

def correggi_nomi_colonne(df, colonne):
    df.columns = colonne
    return df

#CICLO PRINCIPALE 
#----------------------------------------------------
def main(file_gara_raw):
    print("INIZIO FORMATTAZIONE GARA")
    try:
        df = pd.read_excel(file_gara_raw, 
                        sheet_name=0, 
                        dtype={'Ordini di vendita P.IVA': str, 'Items ID Pratica': str})

        # 1. rimuove righe vuote
        df = df.dropna(how='all')

        # 2. forza i formati PRIMA di calcolare ← spostato qui
        df = forza_formato_dati(df)

        # 3. ora calcola il prezzo con i tipi corretti
        subset = calcola_prezzo(df)
        
        # 4. prendi il subset di colonne
        subset = subset.iloc[:, COLONNE]   # ← era df.iloc, perdevi i dati calcolati

        # 5. aggiungi colonne vuote per il template
        subset = aggiungi_colonne_vuote(subset)

        # 6. correggi nomi colonne 
        subset = correggi_nomi_colonne(subset, COLONNE_CORRETTE)  # ← mancava il reassign

        # 7. copia il template
        file_gara = copia_template(MASTER, file=file_gara_raw)

        # 8. popola con df_gara finale
        popola_template(file_gara, subset, SHEET_GARA)
        
        print(Fore.GREEN + "\n ✔ FORMATTAZIONE GARA ESEGUITA CON " + Fore.GREEN + Style.BRIGHT + "SUCCESSO")
    except Exception as e:
        print(f"Si è verificato un errore... --> {str(e)}")
    
    return file_gara, subset
    
if __name__ == "__main__":
    main()