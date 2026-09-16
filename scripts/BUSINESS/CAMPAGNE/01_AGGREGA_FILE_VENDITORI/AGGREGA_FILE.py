import pandas as pd
from pathlib import Path
from openpyxl import load_workbook
from colorama import Fore, init
init(autoreset=True) 

from config import trova_file_campagna, copia_stile_cella, ONEDRIVE_VENDITORI, CARTELLA_RAW_FILE, trova_cartella_campagna



def leggi_file_venditore(file_campagna):
    dati_per_tipologia = {}
    
    with pd.ExcelFile(file_campagna) as excel:
        for nome_foglio in excel.sheet_names:
            df = pd.read_excel(excel, sheet_name=nome_foglio, dtype=str)
            
            # Estrai la tipologia dalla colonna o usa il nome del foglio
            if 'Tipologia' in df.columns and not df.empty:
                tipologia = df['Tipologia'].iloc[0]
            else:
                tipologia = nome_foglio
            
            #aggiusta formattazione p.iva --> aggiugne 0 davanti al numero per arrivare ad 11 caratteri 
            if "Partita_IVA" in df.columns and not df.empty:
                df["Partita_IVA"] = df["Partita_IVA"].str.zfill(11)

            # Aggiungi i dati al dizionario per tipologia
            if tipologia not in dati_per_tipologia:
                dati_per_tipologia[tipologia] = []
            
            # Salva DataFrame E riferimento al file/foglio originale
            dati_per_tipologia[tipologia].append({
                'df': df,
                'file_origine': file_campagna,
                'foglio_origine': nome_foglio
            })
    
    return dati_per_tipologia


def _aggrega_file(files_campagna, cartella_output):

    dati_aggregati = {}

     # 1. Processa ogni file venditore
    for file_campagna in files_campagna:
        venditore = file_campagna.stem.replace("CAMPAGNA_", "")
        print(Fore.LIGHTMAGENTA_EX + f"  → Elaboro {venditore}...")
        
        dati_venditore = leggi_file_venditore(file_campagna)
        
        # 2. Aggrega per tipologia
        for tipologia, lista_dati in dati_venditore.items():
            if tipologia not in dati_aggregati:
                dati_aggregati[tipologia] = []
            dati_aggregati[tipologia].extend(lista_dati)
    
    # 3. Crea i file aggregati
    cartella_output.mkdir(exist_ok=True)
    
    for tipologia, lista_dati in dati_aggregati.items():
        if lista_dati:

            # 4. Concatena tutti i DataFrame
            lista_df = [dati['df'] for dati in lista_dati]
            df_finale = pd.concat(lista_df, ignore_index=True)
            df_finale = df_finale.drop_duplicates()
            
            # 5. Crea file temporaneo con pandas
            file_output = cartella_output / f"COMPILATA_{tipologia}.xlsx"
            df_finale.to_excel(file_output, index=False)
            
            # 6. Riapri con openpyxl per applicare la formattazione
            wb_output = load_workbook(file_output)
            ws_output = wb_output.active
            
            # 7. Prendi il primo file come riferimento per la formattazione
            primo_file = lista_dati[0]['file_origine']
            primo_foglio = lista_dati[0]['foglio_origine']
            wb_origine = load_workbook(primo_file)
            ws_origine = wb_origine[primo_foglio]
            
            # 8. Copia formattazione header (riga 1)
            for col_idx in range(1, ws_output.max_column + 1):
                cella_origine = ws_origine.cell(1, col_idx)
                cella_dest = ws_output.cell(1, col_idx)
                copia_stile_cella(cella_origine, cella_dest)
            
            # 9. Copia formattazione righe dati -- > Usa la prima riga dati come template per tutte le altre
            if ws_origine.max_row >= 2:
                for riga_dest in range(2, ws_output.max_row + 1):
                    for col_idx in range(1, ws_output.max_column + 1):
                        cella_origine = ws_origine.cell(2, col_idx)  # Usa sempre riga 2 come template
                        cella_dest = ws_output.cell(riga_dest, col_idx)
                        copia_stile_cella(cella_origine, cella_dest)
                        # Mantieni il valore originale con il suo tipo
                        if isinstance(cella_origine.value, (int, float)):
                            cella_dest.value = cella_origine.valuez
            
            # 10. Copia larghezza colonne
            for col_idx in range(1, min(ws_origine.max_column, ws_output.max_column) + 1):
                col_letter_origine = ws_origine.cell(1, col_idx).column_letter
                col_letter_dest = ws_output.cell(1, col_idx).column_letter
                if ws_origine.column_dimensions[col_letter_origine].width:
                    ws_output.column_dimensions[col_letter_dest].width = \
                        ws_origine.column_dimensions[col_letter_origine].width
            
            wb_origine.close()
            wb_output.save(file_output)
            
            print(Fore.GREEN + f"✓ Creato: COMPILATA_{tipologia}.xlsx ({len(df_finale)+1} righe)")


#FUNZIONE PER AGGREGARE FILE DA CARTELLA VENDITORI
def aggrega_file_venditori(cartella_ricevuti, cartella_output):
    
    # Leggi tutti i file *.xlsx
    files_campagna = list(cartella_ricevuti.glob("*.xlsx"))
    
    if not files_campagna:
        print("⚠ Nessun file campagna trovato in FILE RICEVUTI")
        return
    

    print(f"Trovati {len(files_campagna)} file campagna da aggregare...")

    _aggrega_file(files_campagna, cartella_output)

#FUNZIONE PER AGGREGARE FILE DA CARTELLA DI RIFERIMENTO
def aggrega_file_compilati(files_campagna, cartella_output):
    
    if files_campagna is None:
        print("⚠ Nessun file campagna trovato in FILE RICEVUTI")
        return
    
    print(f"Trovati {len(files_campagna)} file campagna da aggregare...")
    
    _aggrega_file(files_campagna, cartella_output)


def main(cartella_base, cartella_output):
    
    '''
    permette l'utilizzo in 2 versioni:
        1. legge i file compilati direttamente dalla cartella di riferimento del venditore
        2. legge i file dalla cartella "FILE RICEVUTI", + macchinoso ma necessario se 
           i venditori non lo modificano da teams ma lo inviano  
    '''

    funzionalita = True

    if funzionalita:
        
        file_compilati = []
        # 1. legge i file dalle cartelle di riferimento
        for agente, destinazioni in ONEDRIVE_VENDITORI.items():
            file_path = trova_file_campagna(agente, destinazioni)

            # 2. inserisci in una lista il path di ogni file
            file_compilati.append(file_path)
        

        print("=" * 50)
        print("AGGREGAZIONE FILE VENDITORI")
        print("=" * 50 + "")
    
        # 3. Esegui aggregazione
        aggrega_file_compilati(file_compilati, cartella_output)
        
        print("=" * 50)
        print("✓ Aggregazione completata!")
        print(f"File salvati in: {cartella_output}")
        print("=" * 50 + "\n")

    else:
        
        # 1. dichiarazione/assegnazione path cartella 
        cartella_ricevuti = cartella_base / "FILE RICEVUTI"
    
        # 2. Verifica che esista la cartella FILE RICEVUTI
        if not cartella_ricevuti.exists():
            print("❌ La cartella 'FILE RICEVUTI' non esiste!")
            return
    
        print("=" * 50)
        print("AGGREGAZIONE FILE VENDITORI")
        print("=" * 50)
    
        # 3. Esegui aggregazione
        aggrega_file_venditori(cartella_ricevuti, cartella_output)
        
        print("=" * 50)

        print("✓ Aggregazione completata!")
        print(f"File salvati in: {cartella_output}")
        print("=" * 50)

if __name__ == "__main__":

    
    # dichiarazione/assegnazione path necessari
    cartella_base = Path(CARTELLA_RAW_FILE)
    '''
    trova partendo dalla cartella CAMPAGNE, iterando tutte le cartelle e 
    leggendo i primi due numeri davanti al nome, risce a trovare l'ultima cartella delle campagne creata 
    '''
    cartella_output = trova_cartella_campagna(cartella_base)

    main(cartella_base, cartella_output)
