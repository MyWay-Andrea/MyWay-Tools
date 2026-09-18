from datetime import datetime
from html import escape
from pathlib import Path


ETICHETTE_STATI = {
    "presente_corretta": "Aggiornata anagrafica",
    "da_creare": "Creata anagrafica",
    "da_riassegnare": "Cambiato commerciale + aggiornata anagrafica",
    "presente_commerciale_non_verificabile": (
        "Presente - commerciale da verificare"
    ),
    "partita_iva_non_valida": "Partita IVA non valida",
    "conflitto_commerciale": "Conflitto commerciale",
    "conflitto_identificativi": "P. IVA e custcode non coincidono",
    "duplicata_nel_crm": "Duplicata nel CRM",
    "commerciale_non_mappato": "Commerciale non mappato",
}


CLASSI_STATI = {
    "presente_corretta": "ok",
    "da_creare": "info",
    "da_riassegnare": "warning",
    "presente_commerciale_non_verificabile": "warning",
    "partita_iva_non_valida": "error",
    "conflitto_commerciale": "error",
    "conflitto_identificativi": "error",
    "duplicata_nel_crm": "error",
    "commerciale_non_mappato": "error",
}

SIMBOLI_STATI = {
    "presente_corretta": "✓",
    "da_creare": "+",
    "da_riassegnare": "↻",
    "presente_commerciale_non_verificabile": "?",
    "partita_iva_non_valida": "!",
    "conflitto_commerciale": "⚠",
    "conflitto_identificativi": "≠",
    "duplicata_nel_crm": "⧉",
    "commerciale_non_mappato": "⊘",
}


def testo(valore, predefinito="") -> str:
    if valore is None:
        return predefinito

    stringa = str(valore).strip()

    if not stringa or stringa.lower() == "nan":
        return predefinito

    return stringa


def primo_valore(risultato: dict, *chiavi, predefinito="N/A") -> str:
    for chiave in chiavi:
        valore = testo(risultato.get(chiave))
        if valore:
            return valore

    return predefinito


def genera_cards(riepilogo: dict) -> str:
    cards = []

    for stato, totale in sorted(riepilogo.items()):
        classe = CLASSI_STATI.get(stato, "info")
        etichetta = ETICHETTE_STATI.get(stato, stato)
        simbolo = SIMBOLI_STATI.get(stato, "•")
        cards.append(
            f'<div class="card {classe}">'
            f'<span class="indicatore {classe}" aria-hidden="true">'
            f"{escape(simbolo)}</span>"
            '<div class="card-contenuto">'
            f"<strong>{totale}</strong>"
            f"<span>{escape(etichetta)}</span>"
            "</div></div>"
        )

    return "".join(cards)


def genera_opzioni_esito(risultati: list[dict]) -> str:
    return "".join(
        f'<option value="{escape(esito, quote=True)}">'
        f"{escape(SIMBOLI_STATI.get(stato, '•'))} "
        f"{escape(esito)}</option>"
        for stato, esito in sorted({
            (
                risultato.get("stato"),
                ETICHETTE_STATI.get(
                    risultato.get("stato"),
                    testo(
                        risultato.get("stato"),
                        "Stato non disponibile",
                    ),
                ),
            )
            for risultato in risultati
        }, key=lambda elemento: elemento[1])
    )


def genera_righe_tabella(risultati: list[dict]) -> str:
    righe = []

    for risultato in risultati:
        stato = risultato.get("stato")
        esito = ETICHETTE_STATI.get(
            stato,
            testo(stato, "Stato non disponibile"),
        )
        simbolo = SIMBOLI_STATI.get(stato, "•")
        classe_indicatore = CLASSI_STATI.get(stato, "info")
        classe_riga = ""

        if stato == "da_creare":
            classe_riga = "riga-nuova"
        elif stato == "commerciale_non_mappato":
            classe_riga = "riga-esclusa"

        valori = [
            primo_valore(
                risultato,
                "commerciale",
                predefinito="SENZA COMMERCIALE",
            ),
            primo_valore(risultato, "ragione_sociale"),
            primo_valore(
                risultato,
                "partita_iva",
                "partita_iva_originale",
            ),
            primo_valore(
                risultato,
                "custcode",
                "custcode_originale",
            ),
            primo_valore(risultato, "sede_legale"),
            primo_valore(risultato, "email"),
        ]
        celle = (
            '<td class="cella-stato">'
            f'<span class="indicatore {classe_indicatore}" '
            f'title="{escape(esito, quote=True)}" '
            f'aria-label="{escape(esito, quote=True)}">'
            f"{escape(simbolo)}</span></td>"
        )
        celle += "".join(
            f"<td>{escape(valore)}</td>"
            for valore in valori
        )
        righe.append(
            f'<tr class="{classe_riga}" '
            f'data-stato="{escape(testo(stato), quote=True)}" '
            f'data-esito="{escape(esito, quote=True)}">'
            f"{celle}</tr>"
        )

    if not righe:
        return (
            '<tr class="riga-vuota"><td colspan="7">'
            "Nessuna azienda disponibile.</td></tr>"
        )

    return "".join(righe)


def genera_commerciali_considerati(risultati: list[dict]) -> str:
    commerciali = sorted({
        testo(risultato.get("commerciale"))
        for risultato in risultati
        if (
            risultato.get("stato") != "commerciale_non_mappato"
            and testo(risultato.get("commerciale"))
        )
    }, key=str.lower)

    if not commerciali:
        return '<span class="nessun-commerciale">Nessuno</span>'

    return "".join(
        f'<span class="commerciale-chip">{escape(commerciale)}</span>'
        for commerciale in commerciali
    )


def genera_html(analisi: dict, nome_file_cb: str) -> str:
    risultati = sorted(
        analisi.get("risultati", []),
        key=lambda risultato: (
            0 if risultato.get("stato") == "da_creare" else 1,
            primo_valore(
                risultato,
                "commerciale",
                predefinito="",
            ).lower(),
            primo_valore(
                risultato,
                "ragione_sociale",
                predefinito="",
            ).lower(),
        ),
    )
    cards = genera_cards(analisi.get("riepilogo", {}))
    righe = genera_righe_tabella(risultati)
    opzioni_esito = genera_opzioni_esito(risultati)
    commerciali_considerati = genera_commerciali_considerati(risultati)
    totale_righe = len(risultati)

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Report analisi CB</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: Arial, sans-serif; margin: 0; background: #f4f6f8; color: #17202a; }}
main {{ max-width: 1400px; margin: auto; padding: 28px; }}
h1 {{ margin-bottom: 6px; }}
h2 {{ margin-top: 0; }}
.meta {{ color: #5d6d7e; margin-bottom: 22px; }}
.cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0 28px; }}
.card {{ min-width: 190px; padding: 16px; border-radius: 10px; background: white; border-left: 6px solid #3498db; box-shadow: 0 2px 8px rgba(0, 0, 0, .05); display: flex; align-items: center; gap: 12px; }}
.card-contenuto strong {{ display: block; font-size: 26px; }}
.card-contenuto span {{ font-size: 13px; }}
.ok {{ border-color: #239b56; }}
.warning {{ border-color: #f39c12; }}
.error {{ border-color: #c0392b; }}
.info {{ border-color: #2980b9; }}
.pannello {{ background: white; border-radius: 10px; padding: 18px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0, 0, 0, .05); }}
.barra-tabella {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }}
.azioni-tabella {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
.commerciali-considerati {{ margin: -2px 0 14px; color: #5d6d7e; font-size: 12px; line-height: 1.8; }}
.commerciali-considerati strong {{ color: #34495e; margin-right: 6px; }}
.commerciale-chip {{ display: inline-block; margin: 2px 4px 2px 0; padding: 2px 7px; border-radius: 10px; background: #eef4f8; border: 1px solid #d6e4ec; color: #34495e; }}
.nessun-commerciale {{ font-style: italic; }}
button {{ min-height: 34px; padding: 7px 14px; border: 0; border-radius: 6px; background: #2980b9; color: white; cursor: pointer; font-weight: bold; }}
button:hover {{ background: #1f618d; }}
.pulsante-excel {{ background: #217346; }}
.pulsante-excel:hover {{ background: #185c37; }}
.icona-excel {{ display: inline-block; margin-right: 6px; font-size: 15px; }}
.conteggio {{ color: #34495e; font-weight: bold; }}
.table-wrap {{ overflow-x: auto; border: 1px solid #e5e7e9; border-radius: 8px; }}
table {{ width: 1320px; min-width: 1320px; table-layout: fixed; border-collapse: collapse; }}
th, td {{ padding: 11px 13px; border-bottom: 1px solid #e5e7e9; text-align: left; vertical-align: top; }}
td {{ overflow-wrap: anywhere; }}
th {{ background: #eaf2f8; color: #21313c; }}
.colonna-stato, .cella-stato {{ text-align: center; }}
.indicatore {{ display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; flex: 0 0 30px; border-radius: 50%; color: white; background: #2980b9; font-size: 18px; line-height: 1; font-weight: bold; border: 2px solid transparent; }}
.indicatore.ok {{ background: #239b56; }}
.indicatore.warning {{ background: #f39c12; color: #4d3900; }}
.indicatore.error {{ background: #c0392b; }}
.indicatore.info {{ background: #2980b9; }}
.filtri-intestazione th {{ padding: 7px; background: #f5f9fc; }}
.filtri-intestazione input, .filtri-intestazione select {{ width: 100%; min-width: 120px; height: 34px; padding: 6px 8px; border: 1px solid #bdc3c7; border-radius: 5px; background: white; color: #17202a; font-size: 12px; }}
.filtri-intestazione input:focus, .filtri-intestazione select:focus {{ border-color: #2980b9; outline: 2px solid rgba(41, 128, 185, .15); }}
tbody tr:nth-child(even) {{ background: #f8f9f9; }}
tbody tr:hover {{ filter: brightness(.98); }}
tbody tr.riga-nuova {{ background: #e3f2fd; }}
tbody tr.riga-nuova td:first-child {{ border-left: 6px solid #2980b9; }}
tbody tr.riga-esclusa {{ background: #fff3cd; }}
tbody tr.riga-esclusa td:first-child {{ border-left: 6px solid #f39c12; }}
.riga-vuota td {{ color: #7f8c8d; text-align: center; padding: 24px; }}
@media (max-width: 900px) {{
  main {{ padding: 18px; }}
}}
@media (max-width: 560px) {{
  .card {{ flex: 1 1 140px; }}
  .barra-tabella {{ align-items: stretch; flex-direction: column; }}
}}
</style>
</head>
<body>
<main>
<h1>Report analisi CB</h1>
<div class="meta">File: {escape(nome_file_cb)} · Generato: {datetime.now():%d/%m/%Y %H:%M}</div>
<div class="cards">{cards}</div>

<section class="pannello">
<h2>Dettaglio aziende</h2>
<div class="commerciali-considerati">
  <strong>Commerciali considerati nell'analisi:</strong>
  {commerciali_considerati}
</div>
<div class="barra-tabella">
  <div class="conteggio" id="conteggio-righe">
    Mostrate {totale_righe} righe su {totale_righe}
  </div>
  <div class="azioni-tabella">
    <button type="button" id="reset-filtri">Reset filtri</button>
    <button type="button" id="scarica-excel" class="pulsante-excel">
      <span class="icona-excel" aria-hidden="true">X</span>
      Scarica report Excel
    </button>
  </div>
</div>

<div class="table-wrap">
<table id="tabella-aziende">
  <colgroup>
    <col style="width: 150px">
    <col style="width: 140px">
    <col style="width: 250px">
    <col style="width: 140px">
    <col style="width: 130px">
    <col style="width: 250px">
    <col style="width: 260px">
  </colgroup>
  <thead>
    <tr>
      <th class="colonna-stato">Stato</th>
      <th>COMMERCIALE</th>
      <th>Ragione sociale</th>
      <th>Partita IVA</th>
      <th>Custcode</th>
      <th>Sede legale</th>
      <th>Email</th>
    </tr>
    <tr class="filtri-intestazione">
      <th class="colonna-stato">
        <select id="filtro-esito" aria-label="Filtra esito analisi">
          <option value="">Tutti</option>
          {opzioni_esito}
        </select>
      </th>
      <th><input type="text" id="filtro-commerciale" data-column="1" aria-label="Filtra commerciale" placeholder="Filtra..."></th>
      <th><input type="text" id="filtro-ragione" data-column="2" aria-label="Filtra ragione sociale" placeholder="Filtra..."></th>
      <th><input type="text" id="filtro-piva" data-column="3" aria-label="Filtra partita IVA" placeholder="Filtra..."></th>
      <th><input type="text" id="filtro-custcode" data-column="4" aria-label="Filtra custcode" placeholder="Filtra..."></th>
      <th><input type="text" id="filtro-sede" data-column="5" aria-label="Filtra sede legale" placeholder="Filtra..."></th>
      <th><input type="text" id="filtro-email" data-column="6" aria-label="Filtra email" placeholder="Filtra..."></th>
    </tr>
  </thead>
  <tbody>{righe}</tbody>
</table>
</div>
</section>
</main>

<script>
(function () {{
  const tabella = document.getElementById("tabella-aziende");
  const righe = Array.from(
    tabella.querySelectorAll("tbody tr:not(.riga-vuota)")
  );
  const filtriTesto = Array.from(
    document.querySelectorAll("input[data-column]")
  );
  const filtroEsito = document.getElementById("filtro-esito");
  const conteggio = document.getElementById("conteggio-righe");
  const pulsanteReset = document.getElementById("reset-filtri");
  const pulsanteExcel = document.getElementById("scarica-excel");

  function applicaFiltri() {{
    let mostrate = 0;

    righe.forEach(function (riga) {{
      const soddisfaTesto = filtriTesto.every(function (filtro) {{
        const colonna = Number(filtro.dataset.column);
        const ricerca = filtro.value.trim().toLowerCase();
        const contenuto = riga.cells[colonna].textContent.toLowerCase();
        return !ricerca || contenuto.includes(ricerca);
      }});
      const esitoSelezionato = filtroEsito.value;
      const esitoRiga = riga.dataset.esito;
      const soddisfaEsito = (
        !esitoSelezionato || esitoRiga === esitoSelezionato
      );
      const visibile = soddisfaTesto && soddisfaEsito;

      riga.style.display = visibile ? "" : "none";
      if (visibile) mostrate += 1;
    }});

    conteggio.textContent = (
      "Mostrate " + mostrate + " righe su " + righe.length
    );
  }}

  filtriTesto.forEach(function (filtro) {{
    filtro.addEventListener("input", applicaFiltri);
  }});
  filtroEsito.addEventListener("change", applicaFiltri);
  pulsanteReset.addEventListener("click", function () {{
    filtriTesto.forEach(function (filtro) {{
      filtro.value = "";
    }});
    filtroEsito.value = "";
    applicaFiltri();
  }});

  function escapeXml(valore) {{
    return String(valore)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  }}

  function dataOraFile() {{
    const data = new Date();
    const dueCifre = function (valore) {{
      return String(valore).padStart(2, "0");
    }};
    return (
      data.getFullYear()
      + dueCifre(data.getMonth() + 1)
      + dueCifre(data.getDate())
      + "_"
      + dueCifre(data.getHours())
      + dueCifre(data.getMinutes())
      + dueCifre(data.getSeconds())
    );
  }}

  function numero16(valore) {{
    const risultato = new Uint8Array(2);
    new DataView(risultato.buffer).setUint16(0, valore, true);
    return risultato;
  }}

  function numero32(valore) {{
    const risultato = new Uint8Array(4);
    new DataView(risultato.buffer).setUint32(
      0,
      valore >>> 0,
      true
    );
    return risultato;
  }}

  function unisciArray(parti) {{
    const lunghezza = parti.reduce(function (totale, parte) {{
      return totale + parte.length;
    }}, 0);
    const risultato = new Uint8Array(lunghezza);
    let posizione = 0;
    parti.forEach(function (parte) {{
      risultato.set(parte, posizione);
      posizione += parte.length;
    }});
    return risultato;
  }}

  const tabellaCrc = (function () {{
    const tabella = new Uint32Array(256);
    for (let indice = 0; indice < 256; indice += 1) {{
      let valore = indice;
      for (let bit = 0; bit < 8; bit += 1) {{
        valore = (
          valore & 1
            ? 0xedb88320 ^ (valore >>> 1)
            : valore >>> 1
        );
      }}
      tabella[indice] = valore >>> 0;
    }}
    return tabella;
  }})();

  function crc32(dati) {{
    let crc = 0xffffffff;
    for (let indice = 0; indice < dati.length; indice += 1) {{
      crc = (
        tabellaCrc[(crc ^ dati[indice]) & 0xff]
        ^ (crc >>> 8)
      );
    }}
    return (crc ^ 0xffffffff) >>> 0;
  }}

  function dataOraDos(data) {{
    const anno = Math.max(data.getFullYear(), 1980);
    return {{
      data: (
        ((anno - 1980) << 9)
        | ((data.getMonth() + 1) << 5)
        | data.getDate()
      ),
      ora: (
        (data.getHours() << 11)
        | (data.getMinutes() << 5)
        | Math.floor(data.getSeconds() / 2)
      )
    }};
  }}

  function creaZip(file) {{
    const codifica = new TextEncoder();
    const locali = [];
    const centrali = [];
    const momento = dataOraDos(new Date());
    let offset = 0;

    file.forEach(function (elemento) {{
      const nome = codifica.encode(elemento.nome);
      const dati = codifica.encode(elemento.contenuto);
      const crc = crc32(dati);
      const intestazioneLocale = unisciArray([
        numero32(0x04034b50),
        numero16(20),
        numero16(0x0800),
        numero16(0),
        numero16(momento.ora),
        numero16(momento.data),
        numero32(crc),
        numero32(dati.length),
        numero32(dati.length),
        numero16(nome.length),
        numero16(0),
        nome,
        dati
      ]);
      const intestazioneCentrale = unisciArray([
        numero32(0x02014b50),
        numero16(20),
        numero16(20),
        numero16(0x0800),
        numero16(0),
        numero16(momento.ora),
        numero16(momento.data),
        numero32(crc),
        numero32(dati.length),
        numero32(dati.length),
        numero16(nome.length),
        numero16(0),
        numero16(0),
        numero16(0),
        numero16(0),
        numero32(0),
        numero32(offset),
        nome
      ]);
      locali.push(intestazioneLocale);
      centrali.push(intestazioneCentrale);
      offset += intestazioneLocale.length;
    }});

    const datiLocali = unisciArray(locali);
    const directoryCentrale = unisciArray(centrali);
    const fineDirectory = unisciArray([
      numero32(0x06054b50),
      numero16(0),
      numero16(0),
      numero16(file.length),
      numero16(file.length),
      numero32(directoryCentrale.length),
      numero32(datiLocali.length),
      numero16(0)
    ]);
    return unisciArray([
      datiLocali,
      directoryCentrale,
      fineDirectory
    ]);
  }}

  function nomeColonnaExcel(indice) {{
    let nome = "";
    let numero = indice;
    while (numero > 0) {{
      numero -= 1;
      nome = String.fromCharCode(65 + (numero % 26)) + nome;
      numero = Math.floor(numero / 26);
    }}
    return nome;
  }}

  function cellaExcel(valore, riga, colonna, stile) {{
    const riferimento = nomeColonnaExcel(colonna) + riga;
    return (
      '<c r="' + riferimento + '" t="inlineStr" s="' + stile + '">'
      + '<is><t xml:space="preserve">'
      + escapeXml(valore)
      + "</t></is></c>"
    );
  }}

  function scaricaExcel() {{
    const righeVisibili = righe.filter(function (riga) {{
      return riga.style.display !== "none";
    }});
    const intestazioni = [
      "Stato",
      "COMMERCIALE",
      "Ragione sociale",
      "Partita IVA",
      "Custcode",
      "Sede legale",
      "Email"
    ];
    const datiTabella = righeVisibili.map(function (riga) {{
      const simbolo = riga.cells[0].textContent.trim();
      return [
        simbolo + " " + riga.dataset.esito,
        riga.cells[1].textContent.trim(),
        riga.cells[2].textContent.trim(),
        riga.cells[3].textContent.trim(),
        riga.cells[4].textContent.trim(),
        riga.cells[5].textContent.trim(),
        riga.cells[6].textContent.trim()
      ];
    }});
    const righeXml = [intestazioni].concat(datiTabella)
      .map(function (valori, indiceRiga) {{
        const numeroRiga = indiceRiga + 1;
        const stile = indiceRiga === 0 ? 1 : 2;
        return (
          '<row r="' + numeroRiga + '">'
          + valori.map(function (valore, indiceColonna) {{
            return cellaExcel(
              valore,
              numeroRiga,
              indiceColonna + 1,
              stile
            );
          }}).join("")
          + "</row>"
        );
      }}).join("");
    const ultimaRiga = datiTabella.length + 1;
    const foglioXml = (
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      + '<worksheet xmlns="http://schemas.openxmlformats.org/'
      + 'spreadsheetml/2006/main">'
      + '<dimension ref="A1:G' + ultimaRiga + '"/>'
      + '<sheetViews><sheetView workbookViewId="0">'
      + '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
      + 'state="frozen"/></sheetView></sheetViews>'
      + '<cols>'
      + '<col min="1" max="1" width="34" customWidth="1"/>'
      + '<col min="2" max="2" width="20" customWidth="1"/>'
      + '<col min="3" max="3" width="42" customWidth="1"/>'
      + '<col min="4" max="5" width="20" customWidth="1"/>'
      + '<col min="6" max="6" width="42" customWidth="1"/>'
      + '<col min="7" max="7" width="36" customWidth="1"/>'
      + '</cols><sheetData>' + righeXml + "</sheetData>"
      + '<autoFilter ref="A1:G' + ultimaRiga + '"/>'
      + "</worksheet>"
    );
    const fileXlsx = [
      {{
        nome: "[Content_Types].xml",
        contenuto: (
          '<?xml version="1.0" encoding="UTF-8"?>'
          + '<Types xmlns="http://schemas.openxmlformats.org/'
          + 'package/2006/content-types">'
          + '<Default Extension="rels" ContentType="application/'
          + 'vnd.openxmlformats-package.relationships+xml"/>'
          + '<Default Extension="xml" ContentType="application/xml"/>'
          + '<Override PartName="/xl/workbook.xml" ContentType="application/'
          + 'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          + '<Override PartName="/xl/worksheets/sheet1.xml" '
          + 'ContentType="application/vnd.openxmlformats-officedocument.'
          + 'spreadsheetml.worksheet+xml"/>'
          + '<Override PartName="/xl/styles.xml" ContentType="application/'
          + 'vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          + "</Types>"
        )
      }},
      {{
        nome: "_rels/.rels",
        contenuto: (
          '<?xml version="1.0" encoding="UTF-8"?>'
          + '<Relationships xmlns="http://schemas.openxmlformats.org/'
          + 'package/2006/relationships">'
          + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
          + 'officeDocument/2006/relationships/officeDocument" '
          + 'Target="xl/workbook.xml"/></Relationships>'
        )
      }},
      {{
        nome: "xl/workbook.xml",
        contenuto: (
          '<?xml version="1.0" encoding="UTF-8"?>'
          + '<workbook xmlns="http://schemas.openxmlformats.org/'
          + 'spreadsheetml/2006/main" xmlns:r="http://schemas.'
          + 'openxmlformats.org/officeDocument/2006/relationships">'
          + '<sheets><sheet name="Report" sheetId="1" r:id="rId1"/>'
          + "</sheets></workbook>"
        )
      }},
      {{
        nome: "xl/_rels/workbook.xml.rels",
        contenuto: (
          '<?xml version="1.0" encoding="UTF-8"?>'
          + '<Relationships xmlns="http://schemas.openxmlformats.org/'
          + 'package/2006/relationships">'
          + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
          + 'officeDocument/2006/relationships/worksheet" '
          + 'Target="worksheets/sheet1.xml"/>'
          + '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/'
          + 'officeDocument/2006/relationships/styles" '
          + 'Target="styles.xml"/></Relationships>'
        )
      }},
      {{
        nome: "xl/styles.xml",
        contenuto: (
          '<?xml version="1.0" encoding="UTF-8"?>'
          + '<styleSheet xmlns="http://schemas.openxmlformats.org/'
          + 'spreadsheetml/2006/main">'
          + '<fonts count="2"><font><sz val="11"/><name val="Calibri"/>'
          + '</font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/>'
          + '<name val="Calibri"/></font></fonts>'
          + '<fills count="3"><fill><patternFill patternType="none"/>'
          + '</fill><fill><patternFill patternType="gray125"/></fill>'
          + '<fill><patternFill patternType="solid"><fgColor rgb="FF217346"/>'
          + '<bgColor indexed="64"/></patternFill></fill></fills>'
          + '<borders count="2"><border/><border>'
          + '<left style="thin"><color rgb="FFB7C9BF"/></left>'
          + '<right style="thin"><color rgb="FFB7C9BF"/></right>'
          + '<top style="thin"><color rgb="FFB7C9BF"/></top>'
          + '<bottom style="thin"><color rgb="FFB7C9BF"/></bottom>'
          + '<diagonal/></border></borders>'
          + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" '
          + 'fillId="0" borderId="0"/></cellStyleXfs>'
          + '<cellXfs count="3">'
          + '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" '
          + 'xfId="0"/>'
          + '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" '
          + 'xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>'
          + '<xf numFmtId="49" fontId="0" fillId="0" borderId="1" '
          + 'xfId="0" applyNumberFormat="1" applyBorder="1"/>'
          + '</cellXfs><cellStyles count="1"><cellStyle name="Normal" '
          + 'xfId="0" builtinId="0"/></cellStyles></styleSheet>'
        )
      }},
      {{
        nome: "xl/worksheets/sheet1.xml",
        contenuto: foglioXml
      }}
    ];
    const datiXlsx = creaZip(fileXlsx);
    const blob = new Blob(
      [datiXlsx],
      {{
        type: (
          "application/vnd.openxmlformats-officedocument."
          + "spreadsheetml.sheet"
        )
      }}
    );
    const collegamento = document.createElement("a");
    collegamento.href = URL.createObjectURL(blob);
    collegamento.download = (
      "REPORT_ANALISI_" + dataOraFile() + ".xlsx"
    );
    document.body.appendChild(collegamento);
    collegamento.click();
    document.body.removeChild(collegamento);
    setTimeout(function () {{
      URL.revokeObjectURL(collegamento.href);
    }}, 1000);
  }}

  pulsanteExcel.addEventListener("click", scaricaExcel);

  applicaFiltri();
}})();
</script>
</body>
</html>"""


def salva_report(analisi: dict, nome_file_cb: str, cartella: Path) -> Path:
    cartella.mkdir(parents=True, exist_ok=True)
    file_html = cartella / "REPORT_ANALISI.html"

    file_html.write_text(
        genera_html(analisi, nome_file_cb),
        encoding="utf-8",
    )

    return file_html
