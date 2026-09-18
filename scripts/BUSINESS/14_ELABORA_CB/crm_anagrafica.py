import time

import requests

from config import API_KEY, BASE_URL
from console import avviso, info, progresso, successo


session = requests.Session()


def get_json(endpoint: str, params: dict | None = None):
    if not API_KEY:
        raise ValueError(
            "Chiave API mancante: configura la variabile d'ambiente "
            "CRM_REPORTISTICA_API_KEY_CB"
        )

    parametri = dict(params or {})
    parametri["apikey"] = API_KEY

    risposta = session.get(
        f"{BASE_URL}/{endpoint}",
        params=parametri,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    risposta.raise_for_status()

    return risposta.json()


def estrai_aziende(risposta_json) -> list[dict]:
    if isinstance(risposta_json, list):
        return risposta_json

    if isinstance(risposta_json, dict):
        for chiave in ("items", "data", "results", "companies"):
            aziende = risposta_json.get(chiave)

            if isinstance(aziende, list):
                return aziende

    raise ValueError("Formato JSON dell'anagrafica CRM non riconosciuto")


def leggi_anagrafica_crm(top: int = 100) -> list[dict]:
    aziende = []
    skip = 0

    while True:
        risposta_json = None

        for tentativo in range(1, 6):
            try:
                risposta_json = get_json(
                    "Company/Search",
                    {"top": top, "skip": skip},
                )
                break
            except requests.RequestException as errore:
                if tentativo == 5:
                    raise

                attesa = 5 * tentativo
                avviso(
                    f"Errore CRM: {errore}. "
                    f"Nuovo tentativo tra {attesa} secondi"
                )
                time.sleep(attesa)

        pagina = estrai_aziende(risposta_json)

        if not pagina:
            break

        aziende.extend(pagina)
        progresso(f"Aziende CRM lette: {len(aziende)}")

        if len(pagina) < top:
            break

        skip += top

    print()
    successo(f"Aziende CRM caricate: {len(aziende)}")
    return aziende


if __name__ == "__main__":
    anagrafica = leggi_anagrafica_crm()

    if anagrafica:
        info("Campi disponibili nel primo record:")
        print(sorted(anagrafica[0].keys()))
