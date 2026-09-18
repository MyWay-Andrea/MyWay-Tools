from config import FILE_DIGI
from common.negozi import estrai_df, PATH_TEAM_CONSUMER
from genera_xlsx import genera_xlsx
import pandas as pd 
from colorama import Fore, init
init(autoreset=True)


def main():

    # 1. Estrai df da file 
    df_concat = estrai_df(FILE_DIGI)
    if df_concat.empty:
        print(Fore.RED + "\n ✕  " + Fore.RESET + "DataFrame vuoto"); return

    # 2. check file precedente e incremento
    path_file_digi = PATH_TEAM_CONSUMER / "TOTALE_DIGI.xlsx"

    if path_file_digi.is_file():
        df_backup = pd.read_excel(path_file_digi, dtype=str, engine="openpyxl")
    
    # 3. Genera file excel
    percorso_output = genera_xlsx(df_concat)
    print(
        Fore.GREEN
        + " ✓  "
        + Fore.RESET
        + f"File aggregato creato: {percorso_output}"
    )


if __name__ == "__main__":
    
    main()
