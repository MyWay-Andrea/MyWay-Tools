import requests
import json
import time

API_KEY  = "ppoemfzjqo.JfxgZaAli4Pt73K1xDM80I1aqkFfvxxRkADpZFb"
BASE_URL = "https://app.crmincloud.it/api/v1"

# Se Catalog/Search restituisce pochi campi, metti True per chiamare anche
# Catalog/Get su ogni prodotto trovato.
DETAIL_BY_ID = False

def get_json(endpoint, params=None):
    p = dict(params or {})
    p["apikey"] = API_KEY

    r = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=p,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    r.raise_for_status()
    return r.json()


def get_all_catalog(top=30):
    prodotti = []
    skip = 0
    pagina = 1

    while True:
        batch = get_json("Catalog/Search", {"top": top, "skip": skip})

        if not batch:
            break

        prodotti.extend(batch)
        print(f"Pagina {pagina}: {len(batch)} prodotti | totale {len(prodotti)}")

        if len(batch) < top:
            break

        skip += top
        pagina += 1

    return prodotti


def enrich_catalog_by_id(prodotti):
    dettagli = []

    for index, prodotto in enumerate(prodotti, 1):
        product_id = prodotto.get("id")
        if not product_id:
            dettagli.append(prodotto)
            continue

        try:
            dettagli.append(get_json("Catalog/Get", {"id": product_id}))
        except requests.RequestException as exc:
            print(f"Errore Catalog/Get id={product_id}: {exc}")
            dettagli.append(prodotto)

        if index % 25 == 0:
            print(f"Dettagli catalogo: {index}/{len(prodotti)}")
            time.sleep(1)

    return dettagli


def main():
    catalogo = get_all_catalog()

    if DETAIL_BY_ID:
        catalogo = enrich_catalog_by_id(catalogo)

    print(f"\nTotale prodotti catalogo: {len(catalogo)}")

    if catalogo:
        print("\nCampi disponibili sul primo prodotto:")
        print(sorted(catalogo[0].keys()))

        print("\nPrimo prodotto:")
        print(json.dumps(catalogo[0], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
