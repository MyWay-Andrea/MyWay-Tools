from config import PATH_TEMPLATE
import shutil
import xlwings as xw
import pandas as pd
from pathlib import Path
import psutil
import time 

#ELIMINA PROCESSI EXCEL RIMASTI APERTI
def kill_excel_orfani():
    uccisi = 0
    for processo in psutil.process_iter(["name"]):
        if processo.info['name'] == "EXCEL.EXE":
            processo.kill()
            uccisi += 1
        if uccisi:
            print(f" Chiusi  {uccisi} processi Excel orfani")
            time.sleep(1)

#COPIA TEMPALTE
def copia_template(path_folder, ultimo_giorno):
    path_folder = Path(path_folder)
    path_folder.mkdir(parents=True, exist_ok=True)
    filename = path_folder / f"REPORT_PEDONALITA_{ultimo_giorno}.xlsx"
    shutil.copy2(PATH_TEMPLATE, filename)

    return filename

def converti_date(df, colonne_escluse=None):
    subset = df.copy()
    colonne_escluse = colonne_escluse or []
    for col in subset.columns:
        if col in colonne_escluse:
            continue  # ✅ colonna B resta datetime → Excel la formatta
        if pd.api.types.is_datetime64_any_dtype(subset[col]):
            subset[col] = subset[col].dt.strftime('%Y-%m-%d').fillna('')
    return subset


def scrivi_dati_nei_fogli(file_report, df_db, df_mese, df_settimana):
    fogli = [
        ("FILE DB", df_db),
        ("MESE DB", df_mese),
        ("SETTIMANA DB", df_settimana)
    ]
    
    app = xw.App(visible=False)
    app.display_alerts = False
    app.screen_updating = False
    
    CHUNK_SIZE = 5000
    
    try:
        print(f"  → Apertura file: {file_report}")
        print(f"  → File esiste: {Path(file_report).exists()}")
        wb = xw.Book(file_report)
        
        print(f"  → Workbook aperto, fogli disponibili: {[s.name for s in wb.sheets]}")
        for nome_foglio, df in fogli:
            if df.empty:
                continue
            
            # ✅ rimozione colonne dentro il ciclo, una volta per df
            col_da_rimuovere = [c for c in ["Mese"] if c in df.columns]
            df = df.drop(columns=col_da_rimuovere)
            
            print(f"  → Scrittura '{nome_foglio}': {len(df)} righe...")
            ws = wb.sheets[nome_foglio]

            # RIDIMENSIONAMENTO TABELLE 
            try:
                count = ws.api.ListObjects.Count
                for i in range(1, count + 1):
                    tbl = ws.api.ListObjects.Item(i)
                    ultima_riga = len(df) + 1
                    ultima_col  = len(df.columns)
                    nuovo_range = ws.range((1, 1), (ultima_riga, ultima_col)).address
                    tbl.Resize(ws.range(nuovo_range).api)
                    print(f"    📐 Tabella '{tbl.Name}' ridimensionata → {nuovo_range}")
            except Exception as e:
                print(f"    ⚠️ Ridimensionamento tabella: {e}")

            # scrivi dati a chunk
            for i in range(0, len(df), CHUNK_SIZE):
                chunk = df.iloc[i:i+CHUNK_SIZE].values.tolist()
                ws.cells(i + 2, 1).value = chunk
                print(f"    {min(i+CHUNK_SIZE, len(df))}/{len(df)} righe...")
            
            try:
                ultima_riga_dati = len(df) + 1
                ws.range(
                    ws.cells(2, 2),
                    ws.cells(ultima_riga_dati, 2)
                ).number_format = "dd/mm/yyyy"
                print(f"    📅 Colonna B formattata ({ultima_riga_dati - 1} celle)")
            except Exception as e:
                print(f"    ⚠️ Formattazione colonna B: {e}")
            
            print(f" ✅ '{nome_foglio}' scritto")

        # aggiorna pivot
        print("  → Aggiornamento pivot...")
        try:
            count_pc = wb.api.PivotCaches().Count
            for i in range(1, count_pc + 1):
                try:
                    pc = wb.api.PivotCaches().Item(i)
                    pc.MissingItemsLimit = 0
                    pc.Refresh()
                except Exception as e:
                    print(f"    ⚠️ Cache {i}: {e}")
            
            wb.api.RefreshAll()
            print(" ✅ Pivot aggiornate")
            
            # ✅ ordinamento giorni: basta il foglio SETTIMANA, nessun filtro sul nome pivot
            ORDINE_GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
            print("  → Ordinamento giorni nelle pivot...")
            try:
                sheet_settimana = wb.api.Sheets("SETTIMANA")
                for j in range(1, sheet_settimana.PivotTables().Count + 1):
                    pt = sheet_settimana.PivotTables(j)
                    try:
                        campo_giorno = pt.PivotFields("Giorno")
                        for idx, giorno in enumerate(ORDINE_GIORNI, start=1):
                            try:
                                campo_giorno.PivotItems(giorno).Position = idx
                            except:
                                pass
                        print(f" ✅ Pivot '{pt.Name}' ordinata")
                    except:
                        pass
            except Exception as e:
                print(f"  ⚠️ Ordinamento giorni: {e}")

            # ✅ autofit dopo RefreshAll con screen_updating attivo, altrimenti le pivot non sono ancora renderizzate
            app.screen_updating = True
            for i in range(1, wb.api.Sheets.Count + 1):
                try:
                    wb.api.Sheets(i).Cells.EntireColumn.AutoFit()
                except Exception as e:
                    print(f"    ⚠️ Autofit foglio {i}: {e}")
            print(" ✅ Colonne adattate")

        except Exception as e:
            print(f"  ⚠️ RefreshAll: {e}")
        
        wb.save()
        wb.close()
        print("  ✅ File salvato")
    finally:
        if wb is not None:
            try:
                wb.close()
            except:
                pass
        app.quit() 
    
#FLUSSO PRINCIPALE
#--------------------------------------------------------------
def main(folder_report, df_DB, df_mese, df_settimana, giorno): 
    # 1. recupera path report e crea file base
    path_report = copia_template(folder_report, giorno)
    # 2. popola fogli report ("file_db", "mese_db", "settimana_db")
    print(path_report)
    scrivi_dati_nei_fogli(path_report, df_DB, df_mese, df_settimana)

    return path_report
