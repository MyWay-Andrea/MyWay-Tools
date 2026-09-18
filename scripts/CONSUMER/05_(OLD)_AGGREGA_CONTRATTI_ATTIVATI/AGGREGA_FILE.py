from config import trova_file_da_teams, aggrega_df, crea_lista_df, salva_file_excel, ONEDRIVE_PATH, COLONNE, PATH_TEAM_CONSUMER
    
def main():
    '''
        LOGICA:
        legge i path dei file da teams e li inserisce in una lista, cicla la lista e inserisce nome_negozio e df in un dizionario.
        una volta creato il dizionario, aggrega i file e carica il file nella cartella di teams "TEAM - CONSUMER"
    '''
    # 1. cerca i file dei negozi su teams e carica in una lista
    parametro = "*CHIUSE.xlsx"
    files = trova_file_da_teams(ONEDRIVE_PATH, parametro)

    # 2. cicla la lista ed estrae tutti i df e il negozio 
    lista_df = crea_lista_df(files, COLONNE)

    # 3. cicla il dizionario e aggrega i dati
    df_aggregato = aggrega_df(lista_df)

    # 4. crea e salva il file excel (xlsx)
    nome_file = "TRATTATIVE_CHIUSE.xlsx"
    salva_file_excel(nome_file, df_aggregato, PATH_TEAM_CONSUMER)

if __name__ =="__main__":   
    
    main()