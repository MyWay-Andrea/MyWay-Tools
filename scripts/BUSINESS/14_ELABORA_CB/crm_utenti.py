from config import COMMERCIALI
from console import avviso, dettaglio, successo
from crm_anagrafica import estrai_aziende, get_json


def leggi_utenti_crm(top: int = 100) -> list[dict]:
    utenti = []
    skip = 0

    while True:
        risposta_json = get_json(
            "Account/Search",
            {"top": top, "skip": skip},
        )
        pagina = estrai_aziende(risposta_json)

        if not pagina:
            break

        utenti.extend(pagina)

        if len(pagina) < top:
            break

        skip += top

    return utenti


def crea_mapping_utenti(utenti_crm: list[dict]) -> tuple[dict, dict, list[str]]:
    id_per_alias = {}

    for utente in utenti_crm:
        account_id = utente.get("id")
        nomi_account = list(utente.get("aliases") or [])
        nome_completo = " ".join(
            parte.strip()
            for parte in (
                str(utente.get("name") or ""),
                str(utente.get("surname") or ""),
            )
            if parte.strip()
        )

        if nome_completo:
            nomi_account.append(nome_completo)

        for alias in nomi_account:
            alias_lower = str(alias).strip().lower()

            if alias_lower in id_per_alias:
                raise ValueError(
                    f"Alias CRM duplicato tra più account: {alias}"
                )

            id_per_alias[alias_lower] = account_id

    id_per_commerciale = {}
    commerciale_per_id = {}
    commerciali_non_trovati = []

    for commerciale in COMMERCIALI:
        nome_crm = commerciale["nome_crm"]
        account_id = id_per_alias.get(nome_crm.strip().lower())

        if account_id is None:
            commerciali_non_trovati.append(nome_crm)
            continue

        id_per_commerciale[nome_crm] = account_id
        commerciale_per_id[account_id] = nome_crm

    return (
        id_per_commerciale,
        commerciale_per_id,
        commerciali_non_trovati,
    )


def leggi_mapping_utenti():
    utenti_crm = leggi_utenti_crm()
    return crea_mapping_utenti(utenti_crm)


if __name__ == "__main__":
    id_per_commerciale, _, commerciali_non_trovati = (
        leggi_mapping_utenti()
    )

    successo("Commerciali CRM riconosciuti:")
    for commerciale, account_id in id_per_commerciale.items():
        dettaglio(f"{commerciale}: {account_id}")

    if commerciali_non_trovati:
        avviso("Commerciali non trovati nel CRM:")
        for commerciale in commerciali_non_trovati:
            dettaglio(commerciale)
