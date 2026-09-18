import pandas as pd

#IMPORT FILE FCST
#--------------------------------------------------------
from FCST_VENDITORI_test import main as fcst_venditori
from FCST_GIORGIO_test import main as fcst_giorgio
from config import (
    svuota_cartella, trova_file,
    COLONNA_AGENTE_APP, COLONNA_AGENTE_GARA, COLONNA_AGENTE_OPP, COL_DATA_APPUNTAMENTO, INIZIO_GARA, PATH_ONEDRIVE_FILE,  CARTELLA_OUTPUT, COLONNE_CORRETTE
)

#PRE PRINT COLORATI
from colorama import Fore, Style, init
init(autoreset=True) # Resetta il colore automaticamente dopo ogni print

def main(file_gara, cartella_output_vend, cartella_output_gio, file_opportunita, file_appuntamenti):

    svuota_cartella(cartella_output_vend)
    svuota_cartella(cartella_output_gio)   
    
    print("\nESEGUI FCST_VENDITORI...\n") 
    try:
        fcst_venditori(file_gara, cartella_output_vend, file_opportunita, file_appuntamenti)
    except Exception as e:
        print(f"ERRORE IN FCST_VENDITORI: {e}")
        exit()
    
    print("\nESEGUI FCST_GIORGIO...\n")
    try:
        fcst_giorgio(file_gara, cartella_output_gio, file_opportunita, file_appuntamenti)
    except Exception as e:
        print(f"ERRORE IN FCST_GIORGIO: {e}")
        exit()

if __name__ == "__main__":
    try:
        try:
            file_gara, file_opportunita, file_appuntamenti = trova_file(PATH_ONEDRIVE_FILE)  
            print("FILE PARQUET TROVATI")
        except Exception as e:
            print(f"ERRORE: {e}")
        
        cartella_output_vend = CARTELLA_OUTPUT / "FILE VENDITORI"
        cartella_output_gio = CARTELLA_OUTPUT / "FILE GIORGIO"

        df_gara_completo = pd.read_parquet(file_gara)
        
        df_gara_completo[COLONNA_AGENTE_GARA] = df_gara_completo[COLONNA_AGENTE_GARA].astype(str).str.strip()

        df_gara_col_corrette = df_gara_completo[COLONNE_CORRETTE].copy()
        
        df_opp_completo = pd.read_parquet(file_opportunita)

        df_opp_completo[COLONNA_AGENTE_OPP] = df_opp_completo[COLONNA_AGENTE_OPP].astype(str).str.strip()

        df_app_completo = pd.read_parquet(file_appuntamenti)

        df_app_completo[COLONNA_AGENTE_APP] = df_app_completo[COLONNA_AGENTE_APP].astype(str).str.strip()
        
        df_app_completo[COL_DATA_APPUNTAMENTO] = pd.to_datetime(
            df_app_completo[COL_DATA_APPUNTAMENTO],
            errors="coerce"
        )
        df_app_completo = df_app_completo[df_app_completo[COL_DATA_APPUNTAMENTO] > INIZIO_GARA]

        main(df_gara_completo, cartella_output_vend, cartella_output_gio, df_opp_completo, df_app_completo)
        print(Fore.GREEN + "\nScript eseguito con successo!")
    except Exception as e:
        print(Fore.RED + f"\nErrore durante l'esecuzione dello script: {e}")
        