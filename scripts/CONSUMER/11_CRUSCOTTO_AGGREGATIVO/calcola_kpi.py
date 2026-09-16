from __future__ import annotations

import re
import unicodedata

import pandas as pd

from config import ORDINE_NEGOZI


def _mese_corrente(df: pd.DataFrame, colonna: str, riferimento: pd.Timestamp) -> pd.DataFrame:
    date = df[colonna]
    return df[(date.dt.year == riferimento.year) & (date.dt.month == riferimento.month)].copy()


def _ordina_negozi(df: pd.DataFrame) -> pd.DataFrame:
    ordine = {negozio: indice for indice, negozio in enumerate(ORDINE_NEGOZI)}
    risultato = df.copy()
    risultato["_ORDINE"] = risultato["NEGOZIO"].map(ordine).fillna(len(ordine))
    return risultato.sort_values(["_ORDINE", "NEGOZIO"]).drop(columns="_ORDINE").reset_index(drop=True)


def _normalizza_venditore(valore: object) -> str:
    if pd.isna(valore):
        return "Non Assegnato"

    testo = unicodedata.normalize("NFKC", str(valore))
    testo = testo.replace("\u00A0", " ")
    testo = "".join(
        carattere
        if (
            carattere.isspace()
            or carattere in {"'", "-", "’"}
            or unicodedata.category(carattere).startswith(("L", "M"))
        )
        else " "
        for carattere in testo
    )
    testo = testo.replace("’", "'")
    testo = re.sub(r"\s+", " ", testo).strip(" '-")
    return testo.title() if testo else "Non Assegnato"


def calcola_kpi(
    business: pd.DataFrame,
    target: pd.DataFrame,
    energia: pd.DataFrame,
    gadget: pd.DataFrame,
    digi: pd.DataFrame,
    pedonalita: pd.DataFrame,
    riferimento: pd.Timestamp | None = None,
) -> dict[str, pd.DataFrame | pd.Timestamp]:
    riferimento = (riferimento or pd.Timestamp.today()).normalize()

    business_ins = _mese_corrente(business, "DATA_INSERIMENTO", riferimento)
    # Nel file BUSINESS GIORNALIERO la colonna PUNTI_ATTIVATI
    # (VALORE PUNTI.1 nel foglio TRACCIAMENTO) è già circoscritta al
    # periodo corrente dalle formule del file sorgente. Non va filtrata
    # nuovamente per DATA_ATTIVAZIONE: rettifiche o attivazioni pregresse
    # valorizzate nel periodo verrebbero escluse dal totale e dai negozi.
    business_att = _mese_corrente(
        business,
        "DATA_ATTIVAZIONE",
        riferimento,
    )
    energia_mese = _mese_corrente(energia, "DATA", riferimento)
    gadget_mese = _mese_corrente(gadget[gadget["DATA"].notna()], "DATA", riferimento)
    digi_mese = _mese_corrente(digi, "DATA", riferimento)
    pedonalita_mese = _mese_corrente(pedonalita, "DATA", riferimento)

    ins = business_ins.groupby("NEGOZIO", as_index=False)["PUNTI_INSERITI"].sum()
    att = business_att.groupby("NEGOZIO", as_index=False).agg(
        BUSINESS_ATTIVATO=("PUNTI_ATTIVATI", "sum"),
        UNITA_ATTIVATE=("UNITA_ATTIVATE", "sum"),
    )
    ins = ins.rename(columns={"PUNTI_INSERITI": "BUSINESS_INSERITO"})

    energia_negozi = energia_mese.groupby("NEGOZIO", as_index=False).size()
    energia_negozi = energia_negozi.rename(columns={"size": "ENERGIA"})
    pedo = pedonalita_mese.groupby("NEGOZIO", as_index=False)["PRESENZE"].sum()
    gadget_negozi = gadget_mese.groupby("NEGOZIO", as_index=False).agg(
        GADGET=("DATA", "size"),
        CROSS_SELLING=("CROSS_SELLING", "sum"),
    )
    digi_negozi = digi_mese.groupby("NEGOZIO", as_index=False).size().rename(
        columns={"size": "DIGI"}
    )

    negozi = set(ORDINE_NEGOZI)
    for frame in (business_ins, business_att, energia_mese, gadget_mese, digi_mese, pedonalita_mese):
        negozi.update(frame["NEGOZIO"].dropna().astype(str))
    dashboard = pd.DataFrame({"NEGOZIO": list(negozi)})

    for frame in (ins, att, target, energia_negozi, digi_negozi, pedo, gadget_negozi):
        dashboard = dashboard.merge(frame, on="NEGOZIO", how="left")

    colonne_zero = [
        "BUSINESS_INSERITO",
        "BUSINESS_ATTIVATO",
        "UNITA_ATTIVATE",
        "ENERGIA",
        "DIGI",
        "PRESENZE",
        "GADGET",
        "CROSS_SELLING",
    ]
    for colonna in colonne_zero:
        dashboard[colonna] = pd.to_numeric(dashboard[colonna], errors="coerce").fillna(0)

    giorno = max(riferimento.day, 1)
    giorni_mese = riferimento.days_in_month
    dashboard["PROIEZIONE"] = (
        dashboard["BUSINESS_ATTIVATO"] / giorno * giorni_mese
    )
    dashboard["VAR_TARGET"] = (
        dashboard["PROIEZIONE"] - dashboard["TARGET"]
    ) / dashboard["TARGET"]
    dashboard["RATIO_ENERGIA"] = dashboard["ENERGIA"].div(
        dashboard["PRESENZE"].where(dashboard["PRESENZE"].gt(0))
    )
    dashboard["PERC_CROSS_SELLING"] = dashboard["CROSS_SELLING"].div(
        dashboard["GADGET"].where(dashboard["GADGET"].gt(0))
    )
    dashboard = _ordina_negozi(dashboard)

    dettaglio_business_ins = business_ins.groupby(
        ["NEGOZIO", "FAMIGLIA_PRODOTTO"],
        as_index=False,
        dropna=False,
    ).agg(
        QUANTITA_INSERITA=("QUANTITA", "sum"),
        PUNTI_INSERITI=("PUNTI_INSERITI", "sum"),
    )
    dettaglio_business_att = business_att.groupby(
        ["NEGOZIO", "FAMIGLIA_PRODOTTO"],
        as_index=False,
        dropna=False,
    ).agg(
        QUANTITA_ATTIVATA=("UNITA_ATTIVATE", "sum"),
        PUNTI_ATTIVATI=("PUNTI_ATTIVATI", "sum"),
    )
    dettaglio_business = dettaglio_business_ins.merge(
        dettaglio_business_att,
        on=["NEGOZIO", "FAMIGLIA_PRODOTTO"],
        how="outer",
    )
    dettaglio_business["FAMIGLIA_PRODOTTO"] = dettaglio_business[
        "FAMIGLIA_PRODOTTO"
    ].fillna("NON CLASSIFICATO")
    for colonna in (
        "QUANTITA_INSERITA",
        "PUNTI_INSERITI",
        "QUANTITA_ATTIVATA",
        "PUNTI_ATTIVATI",
    ):
        dettaglio_business[colonna] = pd.to_numeric(
            dettaglio_business[colonna],
            errors="coerce",
        ).fillna(0)
    negozi_presenti = set(
        business["NEGOZIO"].dropna().astype(str)
    )
    ordine_dettaglio_master = [
        "FIDENZA",
        "GALASSIA",
        "EUROSIA",
        "TORRI",
        "CARPI",
        "SASSUOLO",
        "EXTRA",
    ]
    negozi_dettaglio = [
        negozio
        for negozio in ordine_dettaglio_master
        if negozio in negozi_presenti
    ]
    negozi_dettaglio.extend(
        sorted(negozi_presenti.difference(negozi_dettaglio))
    )
    famiglie_presenti = set(
        dettaglio_business["FAMIGLIA_PRODOTTO"].dropna().astype(str)
    )
    ordine_famiglie_master = [
        "VOCE",
        "FISSA",
        "DATI",
        "SOLUTION",
        "GAS",
        "ENERGY",
        "ALTRO",
    ]
    ordine_famiglie = [
        famiglia
        for famiglia in ordine_famiglie_master
        if famiglia in famiglie_presenti
    ]
    ordine_famiglie.extend(
        sorted(famiglie_presenti.difference(ordine_famiglie))
    )
    griglia_dettaglio = pd.MultiIndex.from_product(
        [negozi_dettaglio, ordine_famiglie],
        names=["NEGOZIO", "FAMIGLIA_PRODOTTO"],
    ).to_frame(index=False)
    dettaglio_business = griglia_dettaglio.merge(
        dettaglio_business,
        on=["NEGOZIO", "FAMIGLIA_PRODOTTO"],
        how="left",
    )
    for colonna in (
        "QUANTITA_INSERITA",
        "PUNTI_INSERITI",
        "QUANTITA_ATTIVATA",
        "PUNTI_ATTIVATI",
    ):
        dettaglio_business[colonna] = pd.to_numeric(
            dettaglio_business[colonna],
            errors="coerce",
        ).fillna(0)
    ordine_negozi_dettaglio = {
        negozio: indice
        for indice, negozio in enumerate(negozi_dettaglio)
    }
    ordine_piste = {
        famiglia: indice
        for indice, famiglia in enumerate(ordine_famiglie)
    }
    dettaglio_business["_ORDINE_NEGOZIO"] = dettaglio_business[
        "NEGOZIO"
    ].map(ordine_negozi_dettaglio)
    dettaglio_business["_ORDINE_PISTA"] = dettaglio_business[
        "FAMIGLIA_PRODOTTO"
    ].map(ordine_piste)
    dettaglio_business = dettaglio_business.sort_values(
        ["_ORDINE_NEGOZIO", "_ORDINE_PISTA"],
    ).drop(
        columns=["_ORDINE_NEGOZIO", "_ORDINE_PISTA"],
    ).reset_index(drop=True)

    business_ins_venditori = business_ins.copy()
    business_att_venditori = business_att.copy()
    energia_venditori = energia_mese.copy()
    gadget_venditori = gadget_mese.copy()
    digi_venditori = digi_mese.copy()
    for frame in (
        business_ins_venditori,
        business_att_venditori,
        energia_venditori,
        gadget_venditori,
        digi_venditori,
    ):
        frame["VENDITORE"] = frame["VENDITORE"].map(_normalizza_venditore)

    vend_business_ins = business_ins_venditori.groupby(["NEGOZIO", "VENDITORE"], as_index=False)["PUNTI_INSERITI"].sum()
    vend_business_att = business_att_venditori.groupby(["NEGOZIO", "VENDITORE"], as_index=False)["PUNTI_ATTIVATI"].sum()
    vend_energia = energia_venditori.groupby(["NEGOZIO", "VENDITORE"], as_index=False).size().rename(columns={"size": "ENERGIA"})
    vend_gadget = gadget_venditori.groupby(["NEGOZIO", "VENDITORE"], as_index=False).agg(
        GADGET=("DATA", "size"),
        CROSS_SELLING=("CROSS_SELLING", "sum"),
    )
    vend_digi = digi_venditori.groupby(["NEGOZIO", "VENDITORE"], as_index=False).size().rename(columns={"size": "DIGI"})
    venditori = vend_business_ins.rename(columns={"PUNTI_INSERITI": "BUSINESS_INSERITO"})
    for frame in (
        vend_business_att.rename(columns={"PUNTI_ATTIVATI": "BUSINESS_ATTIVATO"}),
        vend_energia,
        vend_digi,
        vend_gadget,
    ):
        venditori = venditori.merge(frame, on=["NEGOZIO", "VENDITORE"], how="outer")
    for colonna in ("BUSINESS_INSERITO", "BUSINESS_ATTIVATO", "ENERGIA", "DIGI", "GADGET", "CROSS_SELLING"):
        venditori[colonna] = pd.to_numeric(venditori[colonna], errors="coerce").fillna(0)
    venditori["TOTALE_ATTIVITA"] = venditori["ENERGIA"] + venditori["DIGI"] + venditori["GADGET"]
    ordine_negozi_venditori = {
        negozio: indice
        for indice, negozio in enumerate(ORDINE_NEGOZI)
    }
    venditori["_ORDINE_NEGOZIO"] = venditori["NEGOZIO"].map(
        ordine_negozi_venditori
    ).fillna(len(ordine_negozi_venditori))
    venditori = venditori.sort_values(
        [
            "_ORDINE_NEGOZIO",
            "NEGOZIO",
            "BUSINESS_INSERITO",
            "BUSINESS_ATTIVATO",
            "VENDITORE",
        ],
        ascending=[True, True, False, False, True],
    ).drop(columns="_ORDINE_NEGOZIO").reset_index(drop=True)

    giornaliero_ins = business_ins.groupby(["DATA_INSERIMENTO", "NEGOZIO"], as_index=False)["PUNTI_INSERITI"].sum()
    giornaliero_ins = giornaliero_ins.rename(columns={"DATA_INSERIMENTO": "DATA", "PUNTI_INSERITI": "BUSINESS_INSERITO"})
    giornaliero_att = business_att[
        business_att["DATA_ATTIVAZIONE"].notna()
    ].groupby(
        ["DATA_ATTIVAZIONE", "NEGOZIO"],
        as_index=False,
    )["PUNTI_ATTIVATI"].sum()
    giornaliero_att = giornaliero_att.rename(columns={"DATA_ATTIVAZIONE": "DATA", "PUNTI_ATTIVATI": "BUSINESS_ATTIVATO"})
    giornaliero_energia = energia_mese.groupby(["DATA", "NEGOZIO"], as_index=False).size().rename(columns={"size": "ENERGIA"})
    giornaliero_gadget = gadget_mese.groupby(["DATA", "NEGOZIO"], as_index=False).size().rename(columns={"size": "GADGET"})
    giornaliero_digi = digi_mese.groupby(["DATA", "NEGOZIO"], as_index=False).size().rename(columns={"size": "DIGI"})
    giornaliero = giornaliero_ins
    for frame in (giornaliero_att, giornaliero_energia, giornaliero_digi, giornaliero_gadget):
        giornaliero = giornaliero.merge(frame, on=["DATA", "NEGOZIO"], how="outer")
    for colonna in ("BUSINESS_INSERITO", "BUSINESS_ATTIVATO", "ENERGIA", "DIGI", "GADGET"):
        giornaliero[colonna] = pd.to_numeric(giornaliero[colonna], errors="coerce").fillna(0)
    giornaliero = giornaliero.sort_values(["DATA", "NEGOZIO"], ascending=[False, True]).reset_index(drop=True)

    return {
        "riferimento": riferimento,
        "dashboard": dashboard,
        "dettaglio_business": dettaglio_business,
        "venditori": venditori,
        "giornaliero": giornaliero,
        "business": business,
        "business_att": business_att,
        "energia": energia,
        "gadget": gadget,
        "digi": digi,
    }
