from config import trova_raw_file, PATH_PARQUET, PATH_TEMPLATE, VENDITORI, ONEDRIVE_VENDITORI
from prepara_appuntamenti import main as prepara_df
from popola_fogli import main as popola_fogli
from OneDrive import copia_in_onedrive as salva_su_Teams

import shutil
from colorama import Fore, init
init(autoreset = True)

#PER GARANTIRE AGGIORNAMENTO RAPIDO A CONSOLE MENU
import functools, builtins
builtins.print = functools.partial(print, flush=True)


def copia_template(path_template, agente):
    cartella_output = path_template.parents[1] / "report"
    cartella_output.mkdir(parents = True, exist_ok = True)

    filename = cartella_output / f"Appuntamenti_set({agente}).xlsx"
    shutil.copy2(path_template, filename)

    return filename

def filtra_df(agente, df_app, df_corr):
    df_app_filtrato = df_app[df_app["Azienda assegnata a "] == agente]
    df_corr_filtrato = df_corr[df_corr["Azienda assegnata a "] == agente]

    return df_app_filtrato, df_corr_filtrato

def main(df_app, df_corr):
    print("INZIO SCRIPT...")
    for agente in VENDITORI:

        if agente == "G.MANDELLI":
            report = copia_template(PATH_TEMPLATE, agente)
            report_finale = popola_fogli(report, df_app, df_corr, agente)
            salva_su_Teams(report_finale, ONEDRIVE_VENDITORI, agente)
        else: 
            df_app_agente, df_corr_agente = filtra_df(agente, df_app, df_corr)
            if df_app_agente.empty and df_corr_agente.empty:
                print(Fore.RED + f"\n ⚠️ ATTENZIONE !!! df di {agente} risulta vuoto")
                continue 
            elif not df_app_agente.empty and df_corr_agente.empty:
                print(Fore.RED + f" ({agente}) --> 📉 NESSUNO APPUNTAMENTO TROVATO NELLA SETTIMANA CORRENTE....")

            # 1. copia template
            report = copia_template(PATH_TEMPLATE, agente)

            # 2. popola fogli report
            report_finale = popola_fogli(report, df_app_agente, df_corr_agente)

            # 3. salva report su Teams
            salva_su_Teams(report_finale, ONEDRIVE_VENDITORI, agente)

    print(Fore. GREEN + f"\n 🔝 SONO STATI CREATI TUTTI I REPORT PER LA SETTIMANA CORRENTE")

if __name__ == "__main__":

    path_appuntamenti = trova_raw_file(PATH_PARQUET)
    df_app, df_corr = prepara_df(path_appuntamenti)
    main(df_app, df_corr)