from config import trova_file_da_teams, crea_lista_df, aggrega_df, create_dict_sales, popola_template_da_dict, ONEDRIVE_PATH, OUTPUT_PATH, TEMPLATE_PATH, COLONNE_ORDINATE
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

def main():
    '''
    LOGICA:
    La logica di questo script è qualcosa di semolice ma funzionale, legge i file della gara dalle cartelle di teams di riferimento,
    una volta lette inserisce i path all'interno di una lista che poi verrà iterata per creare una lista di df che poi andranno 
    concatenati per formare un unico DF.
    Una volta creato il DF viene copiato il template nella cartella "TEAM CONSUMER", viene aperto dallo script per poter scrivere all'interno 
    i dati, scorre il file per trovare il venditre di riferimento a cui scrivere di fianco i propri valori, così non si cambia l'ordine dei venditori
    '''
    # 1. cerca file da cartelle Teams
    parametro = "*BIZ.xlsx"
    files = trova_file_da_teams(ONEDRIVE_PATH, parametro)
    
    # 2. crea lista df per aggregazione
    lista_df = crea_lista_df(files)

    # 3. aggrega df 
    df_aggregato = aggrega_df(lista_df, COLONNE_ORDINATE)
    
    # 4. genera dict con nome venditore e df con suoi valori filtrati/aggregati
    dict_sales = create_dict_sales(df_aggregato)

    # 5. copia template e popola
    nome_file ="PREMIO_BUSINESS.xlsx"

    popola_template_da_dict(dict_sales, TEMPLATE_PATH, OUTPUT_PATH, nome_file)

if __name__ == "__main__":

    main()