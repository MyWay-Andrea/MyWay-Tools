import pandas as pd

from analisi_aziende import analizza_aziende
from config import (
    CB_RAPIDA,
    CRM_DRY_RUN,
    EMAIL_DRY_RUN,
    PATH_CB_CORRENTE,
    PATH_RAW_CB,
    stampa_stato_dry_run,
)
from console import (
    avviso,
    dettaglio,
    errore,
    info,
    percorso,
    successo,
    titolo,
)
from crm_anagrafica import leggi_anagrafica_crm
from crm_utenti import leggi_mapping_utenti
from invio_report import invia_report
from leggi_pulisci_cb import pulisci_cb, pulisci_dataframe_cb, trova_file_cb_rapido
from report_analisi import salva_report
from cb_sharepoint import sincronizza_output_temporanei


def mostra_anteprima_operazioni(analisi: dict) -> None:
    azioni_per_stato = {
        "da_creare": "CREAZIONE",
        "da_riassegnare": "RIASSEGNAZIONE E AGGIORNAMENTO",
        "presente_corretta": "AGGIORNAMENTO CONSISTENZE",
    }
    operazioni = [
        risultato
        for risultato in analisi.get("risultati", [])
        if risultato.get("stato") in azioni_per_stato
    ]

    avviso("Modalità DRY-RUN: nessuna chiamata API sarà effettuata.")
    info(f"Operazioni simulate: {len(operazioni)}")

    for risultato in operazioni:
        azione = azioni_per_stato[risultato["stato"]]
        azienda = risultato.get("ragione_sociale") or "Senza nome"
        commerciale = (
            risultato.get("commerciale")
            or "Senza commerciale"
        )
        dettaglio(f"{azione}: {azienda} - {commerciale}")


def chiedi_conferma(analisi: dict) -> bool:
    if analisi["conflitti_bloccanti"]:
        errore(
            "Sono presenti conflitti bloccanti. "
            "Controlla il report prima di proseguire."
        )
        return False

    titolo("Conferma operazione")
    avviso("Controlla il report HTML prima di approvare.")
    risposta = input(
        "\nScrivi CONFERMA per approvare le modifiche previste: "
    )
    return risposta.strip() == "CONFERMA"


def main():
    stampa_stato_dry_run()

    if CB_RAPIDA:
        titolo("1. Pulizia CB in memoria (modalita rapida)")
        file_cb = trova_file_cb_rapido()
        df_cb = pulisci_dataframe_cb(file_cb)
        successo(f"File CB pulito senza salvare modifiche: {file_cb.name}")
    else:
        titolo("1. Lettura e pulizia CB")
        file_cb = pulisci_cb()
        df_cb = pd.read_excel(file_cb, dtype=str)

    titolo("2. Lettura anagrafica CRM")
    aziende_crm = leggi_anagrafica_crm()

    titolo("3. Lettura utenti CRM")
    (
        id_per_commerciale,
        commerciale_per_id,
        commerciali_non_trovati,
    ) = leggi_mapping_utenti()
    successo(f"Commerciali CRM associati: {len(id_per_commerciale)}")

    if commerciali_non_trovati:
        avviso("Commerciali configurati ma non trovati nel CRM:")
        for commerciale in commerciali_non_trovati:
            dettaglio(commerciale)

    titolo("4. Analisi aziende")
    analisi = analizza_aziende(
        df_cb,
        aziende_crm,
        id_per_commerciale,
        commerciale_per_id,
    )
    successo(f"Aziende analizzate: {len(analisi['risultati'])}")
    dettaglio(
        f"Righe con commerciale non configurato incluse nel report: "
        f"{analisi['righe_escluse']}"
    )

    for stato, totale in sorted(analisi["riepilogo"].items()):
        dettaglio(f"{stato.replace('_', ' ').title()}: {totale}")

    titolo("5. Generazione report")
    cartella_report = PATH_RAW_CB if CB_RAPIDA else PATH_CB_CORRENTE
    file_html = salva_report(
        analisi,
        file_cb.name,
        cartella_report,
    )
    percorso("Report HTML", file_html)
    sincronizza_output_temporanei()

    if analisi["conflitti_bloccanti"]:
        errore(f"Conflitti bloccanti: {analisi['conflitti_bloccanti']}")
    else:
        successo("Nessun conflitto bloccante")

    if chiedi_conferma(analisi):
        from crm_scritture import esegui_operazioni_su_crm

        successo("Analisi approvata dall'utente")
        titolo("6. Scrittura aziende CRM")

        if CRM_DRY_RUN:
            mostra_anteprima_operazioni(analisi)

        try:
            log_entries = esegui_operazioni_su_crm(
                analisi,
                cartella_log=None if CB_RAPIDA else PATH_CB_CORRENTE,
            )
        except KeyboardInterrupt:
            avviso(
                "Operazioni CRM interrotte dall'utente. "
                "Controlla il log di avanzamento prima di riprovare."
            )
            return
        successi = sum(
            1 for entry in log_entries
            if entry["esito"].startswith("OK")
        )
        errori = sum(
            1 for entry in log_entries
            if entry["esito"] == "FALLITO"
        )
        info(f"Operazioni eseguite: {len(log_entries)}")
        info(f"Successi: {successi}, Errori: {errori}")
        if not CB_RAPIDA:
            from salva_log import salva_log

            log_file = salva_log(log_entries, PATH_CB_CORRENTE)
            percorso("Log", log_file)
            sincronizza_output_temporanei()
    else:
        avviso("Nessuna modifica effettuata sul CRM.")

    titolo("7. Invio report Governance")

    if EMAIL_DRY_RUN:
        avviso("Email in modalità dry-run: verrà solo simulata.")
    else:
        info("Email in modalità reale: il messaggio verrà inviato.")

    invia_report(file_html, analisi)
    sincronizza_output_temporanei()


if __name__ == "__main__":
    main()
