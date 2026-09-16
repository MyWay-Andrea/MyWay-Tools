import pandas as pd
from pathlib import Path
from openpyxl import load_workbook
from datetime import datetime as dt

from config import copia_stile_cella, trova_raw_file, elimina_carica_campagna_agente_teams, ONEDRIVE_VENDITORI, CARTELLA_RAW_FILE
'''

primo script da eseguire, lanciare dopo aver eseguito i seguenti passaggi:
1) aver ricevuto i file delle campagne da Vodafone
2) aver assegnato il venditore dalla CB congelata più recente
3) caricare i file reward e evo voce a Luca che la girerà a Raul
4) aver inserito i file nella cartella CAMPAGNA di riferimento nel team 00_SCAMBIA_DOCUMENTI

'''
def trova_colonna_agente(df):
    for col in df.columns:
        col_lower = str(col).lower()
        if 'agente' in col_lower or 'assegnazione' in col_lower:
            return col
    return None


def normalizza_agente(valore):
    # Rimuove tutto dopo " - " (es. "Mario Rossi - Extra" → "Mario Rossi")
    normalizzato = valore.strip().split(' - ')[0].strip()
    # Rimuove le virgole (es. "Scimone, Riccardo" → "Scimone Riccardo")
    normalizzato = normalizzato.replace(',', '').strip()
    return normalizzato


def leggi_agenti(files_sorgente):
    agenti = []
    for file in files_sorgente:
        df = pd.read_excel(file, dtype=str)
        col = trova_colonna_agente(df)
        if col is None:
            continue
        for valore in df[col].dropna().unique():
            normalizzato = normalizza_agente(valore)
            if normalizzato and normalizzato not in agenti:
                agenti.append(normalizzato)
    return agenti


def filtra_per_agente(file_excel, agente):
    df = pd.read_excel(file_excel, dtype=str)
    
    col = trova_colonna_agente(df)
    if col is None:
        return None, None

    def corrisponde(valore):
        if pd.isna(valore):
            return False
        return normalizza_agente(str(valore)).lower() == agente.lower()

    maschera = df[col].apply(corrisponde)
    indici_filtrati = df[maschera].index.tolist()
    
    if not indici_filtrati:
        return None, None
    
    df_filtrato = df[maschera].copy()
    df_filtrato.insert(0, 'Gestito (Si/No)', 'No')
    df_filtrato.insert(1, 'Concluso (Si/No)', 'No')
    df_filtrato.insert(2, 'Tipologia', file_excel.stem)

    return df_filtrato, indici_filtrati

def crea_campagna_agente(agente, files_sorgente, cartella_output):
    oggi = dt.today().strftime("%Y-%m")
    file_output = cartella_output / f"{oggi}_CAMPAGNA_{agente}.xlsx"
    fogli_creati = {}
    
    for file in files_sorgente:
        df, indici = filtra_per_agente(file, agente)
        if df is not None:
            nome_foglio = file.stem[:31]
            fogli_creati[nome_foglio] = {'df': df, 'indici': indici, 'file_origine': file}
    
    if not fogli_creati:
        print(f"  ⚠ Nessun dato per: {agente}")
        return
    
    with pd.ExcelWriter(file_output, engine='openpyxl') as writer:
        for nome_foglio, dati in fogli_creati.items():
            dati['df'].to_excel(writer, sheet_name=nome_foglio, index=False)
    
    wb_output = load_workbook(file_output)

    for nome_foglio, dati in fogli_creati.items():
        ws_output = wb_output[nome_foglio]
        wb_origine = load_workbook(dati['file_origine'])
        ws_origine = wb_origine.active
        
        # Copia stile header
        for col_idx in range(1, ws_origine.max_column + 1):
            cella_origine = ws_origine.cell(1, col_idx)
            cella_dest = ws_output.cell(1, col_idx + 3)
            copia_stile_cella(cella_origine, cella_dest)
        
        # Copia stile righe dati
        for idx_output, idx_origine in enumerate(dati['indici'], start=2):
            riga_origine = idx_origine + 2
            for col_idx in range(1, ws_origine.max_column + 1):
                cella_origine = ws_origine.cell(riga_origine, col_idx)
                cella_dest = ws_output.cell(idx_output, col_idx + 2)
                copia_stile_cella(cella_origine, cella_dest)
        
        # Copia larghezza colonne (salta le MergedCell)
        for col_idx in range(1, ws_origine.max_column + 1):
            cella = ws_origine.cell(1, col_idx)
            if hasattr(cella, 'column_letter'):
                col_letter_origine = cella.column_letter
                col_letter_dest = ws_output.cell(1, col_idx + 2).column_letter
                ws_output.column_dimensions[col_letter_dest].width = \
                    ws_origine.column_dimensions[col_letter_origine].width
        
        wb_origine.close()
    
    wb_output.save(file_output)
    print(f" ✓ Creato: CAMPAGNA_{agente}.xlsx")
    elimina_carica_campagna_agente_teams(agente, file_output, ONEDRIVE_VENDITORI)
    


def main():
    
    # 1. carica i file dalla cartella 00_SCAMBIO_DOCUMENTI
    cartella_raw, files_sorgente = trova_raw_file(CARTELLA_RAW_FILE)
    cartella_output = cartella_raw / "FILE VENDITORI"
    print("Inizio creazione ...\n")
    
    # 2. crea cartella se non c'è
    cartella_output.mkdir(exist_ok=True)
    
    # 3. legge agenti all'interno dei file e li noramlizza
    agenti = leggi_agenti(files_sorgente)
    print(f"Agenti trovati: {agenti}\n")

    # 4. inizia la creazione dei file campagna per ogni agente
    x = 0
    for agente in agenti:
        crea_campagna_agente(agente, files_sorgente, cartella_output)
        x += 1
    
    print(f"\nSono stati creati {x}/{len(agenti)} file")

if __name__ == "__main__":
    main()
