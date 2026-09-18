import pandas as pd
from pathlib import Path
from openpyxl import load_workbook

from colorama import Fore, Style, init
init(autoreset=True) # Resetta il colore automaticamente dopo ogni print

from config import FILTRO_STATO, LISTA_COLONNE_OPPORTUNITA as LISTA_COLONNE, \
    COLONNA_AGENTE_OPP, copia_template, \
    MASTER_OPPORTUNITA as MASTER, SHEET_OPPORTUNITA, copia_formattaz_cella, DATE_COLS_NAME_OPP as DATE_COLS, \
    copia_su_teams, PERCORSO_TEAMS, svuota_cartella, PATH_RAW_FILE, trova_raw_file

#APPLICA IMPORTO TOTALE
#----------------------------------------------------
def applica_importo_totale(df):
    df.insert(10, "Importo Totale", df.iloc[:, 8] * df.iloc[:, 9])
    return df


#----------------------------------------------------
def filtra_df(df):
    colonna = df.columns[3]
    df_filtrato = df[df[colonna].isin(FILTRO_STATO)].copy()
    df_filtrato = df_filtrato.rename(columns={df_filtrato.columns[3]: COLONNA_AGENTE_OPP})
    return df_filtrato


#----------------------------------------------------
def pulisci_df(df):
    #rimozione prefissi
    df.iloc[:, 0] = df.iloc[:, 0].str.replace("Accounts::::", "", regex=False)
    df.iloc[:, 7] = df.iloc[:, 7].str.replace("Products::::", "", regex = False)

    #gestione date
    df.iloc[:, 4] = pd.to_datetime(df.iloc[:, 4], dayfirst=True).dt.strftime('%d/%m/%Y')
    df.iloc[:, 5] = pd.to_datetime(df.iloc[:, 5], dayfirst=True).dt.strftime('%d/%m/%Y')
    df.iloc[:, 6] = pd.to_datetime(df.iloc[:, 6], dayfirst=True).dt.strftime('%d/%m/%Y')

    #quantita in intero
    df.iloc[:,8] = df.iloc[:,8].astype(int)

    return df

#FORZA FORMATO COLONNE FILE EXCEL
#----------------------------------------------------
def forza_formato_excel(ws):
    for row in range(2, ws.max_row + 1):

        #FORZA COLONNA DATE
        ws.cell(row = row, column = 4).number_format = 'DD/MM/YYYY'
        ws.cell(row = row, column = 5).number_format = 'DD/MM/YYYY'
        ws.cell(row = row, column = 6).number_format = 'DD/MM/YYYY'

        #FORZA COLONNE VALUTA
        ws.cell(row = row, column = 10).number_format = '#,##0.00 €'
        ws.cell(row = row, column = 11).number_format = '#,##0.00 €'

        #FORZA COLONNA P.IVA
        ws.cell(row = row, column = 1).number_format = "@"

#POPOLA IL TEMPLATE CON I DATI PULITI
#----------------------------------------------------
def popola_template(file_opp, df, sheet):
    wb = load_workbook(file_opp)

    ws = wb[sheet]

    #copia formato delle celle della riga "2" e lo copia prima di incollare il valore
    template_stili = {idx_col: ws.cell(row=2, column=idx_col) 
                          for idx_col in range(1, len(df.columns) +2 )}

    #p.iva ad 11 caratteri
    if ' "P.IVA"' in df.columns and not df.empty:
                df[' "P.IVA"'] = df[' "P.IVA"'].str.zfill(11)

    for idx_riga, row_data in enumerate(df.values, start=2):
        for idx_col, valore in enumerate(row_data, start=1):
            cella_destinazione = ws.cell(row=idx_riga, column=idx_col)
            copia_formattaz_cella(template_stili[idx_col], cella_destinazione)
            cella_destinazione.value = valore

    #forza formato colonne file gara finale
    forza_formato_excel(ws)

    #salva i dati        
    wb.save(file_opp)
    wb.close()

#APPLICA COLONNE CORRETET A PARQUET
#--------------------------------------------------
COLONNE_CORRETTE = ['Potenziale cliente (Opportunità)', 'Partita IVA (Opportunità)',
       'Proprietario (Opportunità)', 'Stato (Opportunità)', 'Data creazione',
       'Data chiusura prev. (Opportunità)', 'Data modifica',
       'Prodotto esistente', 'Quantità', 'Prezzo', 'Importo totale',
       'Probabilità (Opportunità)', 'TIPO RELAZIONE']

def correggi_nomi_colonne(df, colonne):
    df.columns = colonne
    return df

def main(file_opportunita_raw):
    df = pd.read_csv(file_opportunita_raw,
                     parse_dates = DATE_COLS,
                      dtype= {' "P.IVA"': str},
                      date_format = '%d/%m/%Y')

    subset = df.iloc[:,LISTA_COLONNE]

    subset = applica_importo_totale(subset)

    subset = filtra_df(subset) 

    subset = pulisci_df(subset) 

    correggi_nomi_colonne(subset, COLONNE_CORRETTE)

    nome = "Opportunita.xlsx"
    file_opportunita = copia_template(MASTER, nome = nome)
    popola_template(file_opportunita, subset, SHEET_OPPORTUNITA)

    #salva su teams il file 'Opportunità.xlsx'
    copia_su_teams(file_opportunita, PERCORSO_TEAMS)

    #salva su temas il file in formato '.parquet'
    copia_su_teams(subset)

    #svuota cartella dal file appena analizzato/formattato
    svuota_cartella(PATH_RAW_FILE, "pportunità")

    print(Fore.GREEN + "\n ✔ FORMATTAZIONE OPPORTUNITA ESEGUITA CON " + Fore.GREEN + Style.BRIGHT + "SUCCESSO")


#percorso_excel = Path(r"C:\Users\Stage\OneDrive - My Way S.r.l\Desktop\AUTOMAZIONI\00_FORMATTA_FCST\00_RAW_FILE\Opportunità.csv")

if __name__ == "__main__":
    file_opportunita_raw = trova_raw_file(PATH_RAW_FILE)
    main(file_opportunita_raw)