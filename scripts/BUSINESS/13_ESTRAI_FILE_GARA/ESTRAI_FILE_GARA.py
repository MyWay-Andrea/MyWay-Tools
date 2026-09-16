import importlib
import os
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
BUSINESS_DIR = SCRIPT_DIR.parent

MODULI_DA_ISOLARE = {
    "config",
    "AGGREGA_STORICO",
    "estrai_gara_API",
    "formatta_gara",
    "estrai_opp_API",
    "formatta_opportunita",
    "estrai_app_API",
    "formatta_appuntamenti",
}


def pulisci_moduli():
    for modulo in MODULI_DA_ISOLARE:
        sys.modules.pop(modulo, None)


def prepara_cartella(cartella: Path):
    pulisci_moduli()
    sys.path.insert(0, str(cartella.resolve()))
    os.chdir(cartella)


def ripristina_ambiente(cwd_precedente: Path, path_precedente: list):
    os.chdir(cwd_precedente)
    sys.path[:] = path_precedente
    pulisci_moduli()


def esegui_in_cartella(cartella: Path, funzione):
    cwd_precedente = Path.cwd()
    path_precedente = list(sys.path)

    prepara_cartella(cartella)
    try:
        return funzione()
    finally:
        ripristina_ambiente(cwd_precedente, path_precedente)


def esegui_gara():
    print("\n" + "=" * 70)
    print("GARA - Estrazione, formattazione e caricamento")
    print("=" * 70)

    cartella = BUSINESS_DIR / "09_ESTRAZIONE_ORDINI_API"

    def flusso_gara():
        config = importlib.import_module("config")
        estrai_gara = importlib.import_module("estrai_gara_API")
        aggrega_storico = importlib.import_module("AGGREGA_STORICO")

        df_gara = estrai_gara.main()
        file_storico = config.trova_file(config.PATH_STORICO_BASI_DATI, "Storico")
        aggrega_storico.main(df_gara, file_storico)

    esegui_in_cartella(cartella, flusso_gara)


def esegui_opportunita():
    print("\n" + "=" * 70)
    print("OPPORTUNITA - Estrazione, formattazione e caricamento")
    print("=" * 70)

    cartella = BUSINESS_DIR / "10_ESTRAZIONE_OPP_API"

    def flusso_opportunita():
        estrai_opp = importlib.import_module("estrai_opp_API")
        formatta_opp = importlib.import_module("formatta_opportunita")
        aggrega_storico = importlib.import_module("AGGREGA_STORICO")

        df_opportunita = estrai_opp.main()
        df_opportunita = formatta_opp.main(df_opportunita)
        aggrega_storico.aggiorna_storico(df_opportunita)

    esegui_in_cartella(cartella, flusso_opportunita)


def esegui_appuntamenti():
    print("\n" + "=" * 70)
    print("APPUNTAMENTI - Estrazione, formattazione e caricamento")
    print("=" * 70)

    cartella = BUSINESS_DIR / "11_ESTRAZIONE_APP_API"

    def flusso_appuntamenti():
        estrai_app = importlib.import_module("estrai_app_API")
        formatta_app = importlib.import_module("formatta_appuntamenti")
        aggrega_storico = importlib.import_module("AGGREGA_STORICO")

        df_appuntamenti = estrai_app.main()
        df_appuntamenti = formatta_app.main(df_appuntamenti)
        aggrega_storico.aggiorna_storico(df_appuntamenti)

    esegui_in_cartella(cartella, flusso_appuntamenti)


def main():
    inizio = time.perf_counter()
    print("=== Avvio estrazione completa file gara ===")

    esegui_gara()
    esegui_opportunita()
    esegui_appuntamenti()

    durata = time.perf_counter() - inizio
    print("\n" + "=" * 70)
    print(f"Estrazione completa terminata in {durata:.2f} secondi")
    print("=" * 70)


if __name__ == "__main__":
    main()
