import unittest

import pandas as pd

from archivio_storico import (
    chiudi_periodi_precedenti,
    prepara_blocco,
    riconcilia_periodo_chiuso,
)
from config import COLONNE_CORRETTE_STORICO


def _riga(id_ordine, data_attivazione, id_riga=None):
    riga = {colonna: pd.NA for colonna in COLONNE_CORRETTE_STORICO}
    riga.update({
        "ID ordine (Ordine)": id_ordine,
        "ID Pratica": f"P-{id_ordine}",
        "Prodotto esistente": "Prodotto test",
        "Data Attivazione": data_attivazione,
        "Importo totale": 10,
    })
    if id_riga is not None:
        riga["ID Riga CRM"] = id_riga
    return riga


class ArchivioStoricoTest(unittest.TestCase):
    def test_riga_senza_attivazione_slitta_al_periodo_corrente(self):
        df = pd.DataFrame([_riga("TR40001", None, "R1")])
        archivio = prepara_blocco(
            df,
            fonte="API",
            stato_archivio="CORRENTE",
            anno_default=2026,
            trimestre_default=3,
        )

        risultato = chiudi_periodi_precedenti(archivio, 2026, 4)

        self.assertEqual(risultato.iloc[0]["Stato Archivio"], "CORRENTE")
        self.assertEqual(risultato.iloc[0]["Anno Gara"], 2026)
        self.assertEqual(risultato.iloc[0]["Trimestre Gara"], 4)
        self.assertEqual(risultato.iloc[0]["Periodo Gara"], "Ott - Dic")
        self.assertTrue(pd.isna(risultato.iloc[0]["Data Chiusura Gara"]))

    def test_chiude_solo_riga_attivata_nel_periodo_precedente(self):
        df = pd.DataFrame([_riga("TR40001", "2026-09-30", "R1")])
        archivio = prepara_blocco(
            df,
            fonte="API",
            stato_archivio="CORRENTE",
        )

        risultato = chiudi_periodi_precedenti(archivio, 2026, 4)

        self.assertEqual(risultato.iloc[0]["Stato Archivio"], "CHIUSO")
        self.assertEqual(risultato.iloc[0]["Trimestre Gara"], 3)
        self.assertTrue(pd.notna(risultato.iloc[0]["Data Chiusura Gara"]))

    def test_snapshot_sostituisce_interamente_il_periodo(self):
        storico_q3 = pd.DataFrame([
            _riga("TR40001", "2026-07-01", "R1"),
            _riga("TR40002", "2026-08-01", "R2"),
            _riga("TR40003", "2026-09-01", "R3"),
        ])
        corrente_q4 = pd.DataFrame([
            _riga("TR40004", "2026-10-01", "R4"),
        ])
        archivio = pd.concat([
            prepara_blocco(storico_q3, "API", "CHIUSO"),
            prepara_blocco(corrente_q4, "API", "CORRENTE"),
        ], ignore_index=True)
        chiusura = pd.DataFrame([
            _riga("TR40001", "2026-07-01", "R1"),
            _riga("TR40002", "2026-08-01", "R2"),
        ])

        risultato = riconcilia_periodo_chiuso(
            archivio,
            chiusura,
            2026,
            3,
        )
        q3 = risultato.loc[
            risultato["Anno Gara"].eq(2026)
            & risultato["Trimestre Gara"].eq(3)
        ]

        self.assertEqual(len(q3), 2)
        self.assertTrue(q3["Stato Archivio"].eq("CHIUSO").all())
        self.assertEqual(len(risultato), 3)


if __name__ == "__main__":
    unittest.main()
