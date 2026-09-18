from config import trova_file, create_aggregate_df, normalize_df, write_file_xlsx, delete_old_file, PATH_TEAM_CONSUMER,  ONEDRIVE_PATH
from colorama import Fore, init
import sys
init(autoreset = True)

def main(files_list:list):

    # 1. legge i file e aggrega in un unico df
    try:
        df = create_aggregate_df(files_list)
    except Exception as e:
        print(Fore.RED + f" ❌ Errore: --> {e}")

    # 2. normalizza colonne e controlla foramti
    df = normalize_df(df)

    # 3. elimna file vecchio
    ricerca = "TRACCIAMENTO_PISTA_BIZ*xlsx"
    delete_old_file(PATH_TEAM_CONSUMER, ricerca)

    # 4. aggrega df per negozio (aggregato)
    if not df is None:
        write_file_xlsx(df, PATH_TEAM_CONSUMER)
    else:
        print(Fore.RED + "Il df è None, non posso continaure...")
        sys.exit(1)
    
    
if __name__ == "__main__":
    print("")
    files = trova_file(ONEDRIVE_PATH)
    main(files)