# MyWay Tools - README

Applicazione interna per avviare e gestire gli script operativi MyWay da un unico pannello.

Gli script operativi attivi sono versionati nella cartella `scripts/` e inclusi nella build. La cartella **MyWay Tools su Teams/SharePoint**, configurata dall'utente, rimane dedicata ai file raw, ai dati condivisi, agli output e ai segreti non pubblicabili.

## Struttura Principale

### `menu.py`

E' il pannello principale dell'applicazione.

Contiene:

* configurazione dei percorsi degli script;
* struttura delle sezioni del menu;
* card/pulsanti che lanciano gli script;
* terminale integrato per mostrare l'output;
* avvio del controllo aggiornamenti tramite `updater.py`.

### Interfaccia desktop

L'entrypoint usa `OperationsWindow`: sidebar, elenco ricercabile e dettaglio
integrato sono realizzati con PySide6/Qt Widgets. `ActivitySpec` mantiene le
attività reali e i relativi requisiti; `ModernHubPage` gestisce filtri e selezione.
Il tema QSS, le dimensioni e le icone disegnate con QPainter sono in `ui_theme.py`;
`ui_widgets.py` contiene il componente per i percorsi lunghi con tooltip.
I due moduli sono importati direttamente e vengono rilevati da PyInstaller,
senza nuove dipendenze o risorse esterne da aggiungere a `Menu.spec`.

Il dettaglio prepara i file tramite il gestore RAW esistente. La verifica CB
riutilizza lo stesso controllo SharePoint, ora condiviso con il dialogo precedente
tramite `SharePointCheck`; i risultati arrivano sul thread Qt. Una verifica positiva
abilita l'avvio esplicito. `MainWindow` e le altre classi precedenti sono conservate.

Il terminale conserva i log durante la navigazione. La barra rimane visibile quando
è nascosto; **Mostra/Nascondi** e il divisore consentono di espanderlo e ridimensionarlo.
Ogni avvio lo riapre. Il blocco dei pulsanti persiste durante timer, ricerca e cambio
sezione: questa correzione UI evita il precedente riarmo involontario durante
un'elaborazione. Il motore subprocess, i percorsi operativi e le configurazioni
restano invariati.

Test di regressione UI (richiedono PySide6, senza eseguire script aziendali):

```powershell
python -B -m unittest discover -s tests -v
# Controllo aggiuntivo del layout con scaling Qt:
$env:QT_SCALE_FACTOR = '1.5'
python -B -m unittest discover -s tests -v -k resize
```

I test usano cartelle temporanee, risposte SharePoint simulate e subprocess innocui.
Coprono anche l'entrypoint e il richiamo dell'updater con il download disattivato.
`MYWAY_UI_SCREENSHOTS` permette di salvare schermate nelle dimensioni 1280×800,
1600×900, 1920×1080 e 1024×640. Il rendering offscreen e `QT_SCALE_FACTOR` non
sostituiscono una prova su monitor Windows con DPI diversi, né un collaudo
dell'installer o delle credenziali SharePoint reali.

Nel collaudo del 23 ottobre 2026 i 10 test sono passati anche con il runtime
di distribuzione (`C:\TEMP\_runtime`, Python 3.14.3 / PySide6 6.11.1).
Restano due avvisi del codice/configurazione preesistenti, fuori dall'intervento UI:
il motore subprocess può emettere `ResourceWarning` per lo stream stdout non
chiuso esplicitamente; PyInstaller segnala la voce `site-packages` in `pathex`
di `Menu.spec` come deprecata in vista della versione 7. Il primo avviso non
ha impedito i test; il secondo non ha impedito la build con il runtime previsto.

### `updater.py`

Gestisce l'aggiornamento automatico dell'applicazione.

All'avvio controlla:

* la versione locale da `version.txt`;
* la versione online da GitHub, leggendo `main/version.txt`.

Se trova una versione piu' recente, scarica il `setup.exe` dalla latest release GitHub e lo esegue in modalita' silenziosa.

### `version.txt`

Contiene la versione corrente dell'applicazione.

Deve essere aggiornata a ogni nuova release, per esempio:

```txt
1.0.14
```

### `setup.iss`

File di configurazione Inno Setup.

Definisce:

* nome applicazione;
* versione installer (`AppVersion`);
* cartella di installazione;
* file da includere nell'installer;
* collegamenti Start/Desktop;
* generazione del file `installer_output\setup.exe`.

### `Menu.spec`

File di configurazione PyInstaller.

Definisce:

* file Python principale da compilare (`menu.py`);
* runtime Python da usare (`C:\TEMP\_runtime`);
* file dati inclusi nell'app (`version.txt`, `logo.ico`);
* hidden import necessari;
* nome finale dell'applicazione (`MyWayTools`).

### `requirements_runtime.txt`

Elenco delle librerie installate nel runtime portabile.

Il file viene usato da `build.bat` per aggiornare le dipendenze dentro:

```txt
C:\TEMP\_runtime
```

### `build.bat`

Script da lanciare per creare una nuova build e compilare l'installer.

Automatizza i passaggi tecnici principali, descritti sotto.

### `aggiorna_scripts.ps1`

Sincronizza dalla cartella `SCRIPT` di lavoro soltanto i progetti richiamati
dal menu e le dipendenze condivise. Elimina dalla copia del repository i
progetti non attivi, ma conserva l'eventuale file locale `scripts/.env`.

Esempio da PowerShell, eseguito dalla cartella del repository:

```powershell
.\aggiorna_scripts.ps1 -Origine "C:\percorso\MyWay Tools\SCRIPT"
```

La cartella indicata con `-Origine` deve contenere direttamente le sottocartelle
`BUSINESS`, `CONSUMER` e i file condivisi `config_env.py` e
`graph_sharepoint.py`. Lo script verifica prima che tutti i progetti necessari
siano presenti; solo dopo sostituisce la copia locale.

### `dist\`

Cartella generata da PyInstaller.

Dopo la build contiene:

```txt
dist\MyWayTools\MyWayTools.exe
dist\MyWayTools\_runtime\
```

### `installer_output\`

Cartella generata da Inno Setup.

Contiene l'installer finale da caricare su GitHub:

```txt
installer_output\setup.exe
```

## Cosa Fa `build.bat`

Quando si lancia `build.bat`, vengono eseguiti automaticamente questi passaggi.

### 1. Aggiorna le dipendenze nel runtime

Esegue:

```bat
C:\TEMP\_runtime\python.exe -m pip install -r requirements_runtime.txt --no-warn-script-location
```

Questo installa o aggiorna le librerie richieste dentro il runtime portabile, non nel Python di sistema.

### 2. Compila l'app con PyInstaller

Esegue:

```bat
C:\TEMP\_runtime\python.exe -m PyInstaller Menu.spec --clean -y
```

PyInstaller legge `Menu.spec` e genera la cartella:

```txt
dist\MyWayTools\
```

### 3. Copia il runtime nella build

Esegue una copia di:

```txt
C:\TEMP\_runtime
```

dentro:

```txt
dist\MyWayTools\_runtime\
```

Questo rende l'app portabile: l'utente finale non deve installare Python o librerie.

### 4. Compila l'installer con Inno Setup

Esegue:

```bat
C:\Users\Stage\AppData\Local\Programs\Inno Setup 6\ISCC.exe setup.iss
```

Il risultato finale viene creato in:

```txt
installer_output\setup.exe
```

## Prerequisiti Per La Build

Prima di lanciare `build.bat`, verificare che esistano:

```txt
C:\TEMP\_runtime\python.exe
C:\Users\Stage\AppData\Local\Programs\Inno Setup 6\ISCC.exe
```

Se uno dei due percorsi manca, `build.bat` non puo' completare la build.

## Come Aggiornare La Versione

### Passaggi manuali prima della build

1. Modificare il codice necessario, per esempio `menu.py`.
2. Aggiornare `version.txt` con la nuova versione.
3. Aggiornare `AppVersion` in `setup.iss` con la stessa versione.
4. Se sono state aggiunte nuove librerie Python, aggiornare `requirements_runtime.txt`.

Esempio:

```txt
version.txt        -> 1.0.14
setup.iss          -> AppVersion=1.0.14
GitHub release tag -> v1.0.14
```

### Build automatizzata

Lanciare:

```bat
build.bat
```

Questo aggiorna il runtime, compila l'eseguibile, copia `_runtime` nella cartella `dist` e genera l'installer `installer_output\setup.exe`.

### Passaggi manuali dopo la build

1. Verificare che sia stato creato:

```txt
installer_output\setup.exe
```

2. Creare una nuova release GitHub con tag coerente, per esempio:

```txt
v1.0.14
```

3. Caricare nella release il file:

```txt
installer_output\setup.exe
```

4. Fare commit e push dei file modificati.

Esempio:

```bat
git add menu.py version.txt setup.iss requirements_runtime.txt README.md
git commit -m "v1.0.14"
git push
```

Adattare `git add` ai file realmente modificati.

## Flusso Di Aggiornamento Automatico

L'app installata controlla gli aggiornamenti tramite `updater.py`.

Il flusso e':

1. legge la versione locale da `version.txt`;
2. legge la versione online da GitHub:

```txt
https://raw.githubusercontent.com/MyWay-stage/MyWay-Tools/main/version.txt
```

3. se la versione online e' piu' recente, scarica:

```txt
https://github.com/MyWay-stage/MyWay-Tools/releases/latest/download/setup.exe
```

4. esegue l'installer in silenzioso;
5. riapre l'app aggiornata.

Per questo motivo devono essere coerenti:

```txt
version.txt
setup.iss -> AppVersion
GitHub latest release -> setup.exe
```

## Note Operative

* La build include esplicitamente soltanto gli script operativi richiamati dal menu e le loro dipendenze condivise.
* `scripts/.env`, cache, file di prova e progetti storici non vengono inclusi nell'installer.
* SharePoint continua a contenere input, output e file `.env`; questi ultimi non vengono copiati nella repository.
* Le modifiche a `menu.py`, agli script, `updater.py`, `Menu.spec`, `setup.iss`, `requirements_runtime.txt` o `version.txt` richiedono una nuova build e una nuova release.
* L'installer richiede privilegi amministrativi per installare in `Program Files`.

## Centro operativo: preferiti, storico e workflow

L'entrypoint distribuito rimane `menu.py` → `OperationsWindow` → `ModernHubPage`.
Le vecchie classi di schermata restano per compatibilità, ma non vengono istanziate
dall'avvio corrente. Il checkpoint Git prima di questa evoluzione è `fe903a7`;
il repository era pulito e l'ultimo intervento era il restyling `f93c361`.

Oggi contiene inizialmente Estrai file gara, Forecast Business, Formatta pedonalità,
Cruscotto tracciamento e Cruscotto giornaliero. Le stelle aggiungono/rimuovono
preferiti immediatamente, senza avviare l'attività. Il catalogo resta unico;
Business, Consumer, Campagne e Tutte le attività mantengono le stesse procedure.
Storico, Workflow e Riepilogo sono voci aggiuntive nella navigazione.

### Profilo persistente

Tutti i nuovi file sono in `%APPDATA%\MyWayTools`; `config.json` mantiene il suo
schema e viene aggiornato soltanto quando si cambia la configurazione RAW.

| File | Schema e contenuto |
| --- | --- |
| `preferences.json` | `schema_version: 1`, `favorites: [ID...]`; ordine conservato, anche lista vuota valida |
| `history.db` | SQLite `PRAGMA user_version=2`; tabelle `runs` e `workflow_runs` |
| `history_settings.json` | `schema_version: 1`, `retention_days: 90`, `log_mode: "summary"`, `max_log_chars: 64000` |
| `workflows.json` | `schema_version: 1`, `workflows: []` al primo avvio |
| `execution.lock` | Lock transitorio Qt per impedire esecuzioni contemporanee tra finestre/processi dello stesso profilo |

Le scritture JSON sono atomiche. Un file preferenze corrotto viene conservato come
`preferences.invalid-<uuid>.json` prima del ripristino dei cinque valori iniziali.
Gli ID sconosciuti vengono ignorati nella vista, ma conservati su disco per non
perdere preferenze di attività temporaneamente assenti. Cambiare un titolo non
cambia l'ID. Una configurazione workflow non valida viene conservata e blocca
l'avvio finché non viene corretta; nessuna catena viene riparata eliminando passaggi.

`runs` conserva ID, ID/nome attività, avvio/fine in UTC, durata in secondi,
esito (`completato`, `errore`, `interrotto`, `in_esecuzione`), exit code nullable,
log, ID esecuzione workflow e indice del passaggio. Le date sono mostrate nel fuso
locale di Windows. `workflow_runs` conserva nome, sequenza, indice raggiunto ed
esito complessivo. Le esecuzioni rimaste aperte dopo un arresto dell'app vengono
marcate interrotte al successivo avvio libero da altri esecutori: non ripartono.
In questo caso fine e durata restano sconosciute (`NULL`, visualizzato come «—»),
senza inventare l'istante effettivo dell'arresto.

Lo storico è filtrabile per attività/esito, ordinabile per data e paginato; il
doppio clic apre dettaglio e log. La dashboard calcola i valori sull'intero storico
ancora conservato. Il tasso di successo è completate / concluse (interrotte incluse,
esecuzioni in corso escluse); mostra inoltre le ultime cinque e le più frequenti.

### Log e conservazione

Il valore predefinito `log_mode: "summary"` salva soltanto eventi di avvio, esito e
diagnostica del servizio. L'output originale degli script rimane nel terminale
della sessione e non viene modificato nei file originali. È una scelta di
minimizzazione: alcuni script stampano intere tabelle di dati aziendali.

Per conservare anche l'output, impostare `log_mode: "redacted"` in
`history_settings.json` a programma chiuso. Vengono oscurati segreti noti nelle
variabili di credenziali e nel `.env` del profilo, token riconoscibili e indirizzi
email. Il mascheramento **non garantisce** la rimozione di tutti i dati riservati;
non abilitare questa modalità senza valutare gli output degli script coinvolti.
Il limite è per esecuzione (predefinito 64.000 caratteri); i log oltre il limite
non sono conservati. `retention_days` accetta da 1 a 3650 giorni. Il pulsante
Elimina storico elimina registrazioni concluse e log, mantenendo quelle in corso;
usa secure-delete, checkpoint e compattazione SQLite, senza promettere cancellazione
forense di backup o copie del filesystem.

### Configurare un workflow

Aprire **Workflow → Nuovo**, assegnare un nome, aggiungere attività e usare
Sposta su/Sposta giù per ordinarle. Salvare e poi premere **Avvia workflow**.
Il salvataggio non avvia nulla. Sono possibili modifica, eliminazione e ricarica.
Verificare prima le dipendenze operative: non sono predisposte catene aziendali.

Il formato su disco accetta ID semplici oppure passaggi con controlli output.
Esempio di sola struttura (non viene installato né avviato automaticamente):

```json
{
  "schema_version": 1,
  "workflows": [{
    "id": "sequenza-scelta-dall-utente",
    "name": "La mia sequenza",
    "steps": [
      {"activity_id": "estrai_file_gara"},
      {"activity_id": "forecast_business"}
    ]
  }]
}
```

Un passaggio può aggiungere `"outputs": [{"folder": "C:\\Reports",
"pattern": "*.xlsx", "min_count": 1, "changed": true}]`. La cartella deve essere
assoluta; `changed` è true per default e richiede file nuovi o modificati dopo
l'istantanea precedente all'avvio, evitando di accettare output vecchi. Questi
controlli si configurano nel file JSON e vengono preservati dall'editor grafico.
Sono controlli di presenza/aggiornamento, non di correttezza dei contenuti Excel
o delle pubblicazioni remote. Per verifiche applicative specifiche il catalogo
offre `ActivitySpec.output_validator`, eseguito nel worker dopo exit 0.

Ogni passaggio verifica nuovamente script, requisiti RAW e, per Elabora CB,
SharePoint prima di eseguire. Qualsiasi errore arresta la catena. Sono riconosciuti
anche i messaggi di errore della conformità pedonalità e dei report forecast
saltati, che gli script possono emettere con exit 0. Gli script restano invariati.
**Interrompi workflow** termina solo l'albero di processi appartenente al lancio:
su Windows viene usato un Job Object assegnato prima di riprendere il processo.

### Architettura e verifiche

* `operational_preferences.py`: preferiti e JSON atomico.
* `activity_status.py`: stato condiviso, watcher, debounce e fallback di 30 secondi;
  verifiche locali in worker, controllo remoto esplicito e ripetuto prima dell'avvio.
* `execution_service.py` / `process_lifecycle.py`: unico avvio, lock, lifecycle,
  log e interruzione. La firma pubblica `lancia_script()` resta compatibile; il
  callback booleano viene consegnato nel thread Qt e il risultato resta asincrono,
  anche per script mancanti. Il bootstrap `runpy` degli script è conservato.
* `execution_history.py`, `operations_views.py`: SQLite, storico e dashboard;
  le letture delle viste avvengono in background con richieste accorpate.
* `workflow_service.py`, `workflow_views.py`: definizioni, sequenza ed editor.
* `ui_theme.py`: icone QPainter scalabili e palette centralizzata per ID; nessuna
  risorsa remota, font proprietario o dipendenza QtSvg aggiuntiva.

`_REL_PATHS`, nomi degli script, autenticazione, funzioni SharePoint, sincronizzazione
`aggiorna_scripts.ps1`, updater e versioni di release non sono stati modificati.
L'unica modifica al packaging è l'espansione filtrata dei dati in `Menu.spec`
tramite `packaging_assets.py`: mantiene sorgenti, quattro JSON applicativi e due
template, escludendo cache, `.env` e cartelle output con dati operativi preesistenti.
I file originali restano nel repository. I nuovi moduli sono raccolti dagli import
Python ordinari; nessun dato del profilo utente entra nel pacchetto.

Eseguire i test con un Python dotato di PySide6 e psutil:

```powershell
& C:/TEMP/_runtime/python.exe -B -m unittest discover -s tests -v
```

I test usano profili temporanei, script innocui e risposte SharePoint simulate.
Coprono preferiti, errori JSON, UI, watcher, preflight, cronologia, dashboard,
errori/interrupt dei subprocess, isolamento dei figli, workflow e filtri packaging.
Impostare `MYWAY_UI_SCREENSHOTS` per salvare schermate a 1280×800, 1600×900,
1920×1080 e 1024×640; sono inclusi controlli del rendering delle icone a DPI frazionari.
`tests/smoke_frozen.py <percorso-exe>` verifica l'avvio congelato con profilo
isolato e proxy locale non disponibile per impedire download dell'updater.

Non vengono eseguiti processi aziendali reali, autenticazioni SharePoint o invii
email di produzione. Il collaudo con tali sistemi, i contenuti effettivi degli
output aziendali e l'installazione/aggiornamento Inno Setup richiedono verifica
operativa dedicata prima di pubblicare una release.

Verifica dell'evoluzione del centro operativo (23 ottobre 2026): 32 test automatici
superati, build PyInstaller pulita e avvio dell'eseguibile con profilo isolato
riusciti. Confrontato il bytecode congelato di 11 moduli con i sorgenti definitivi;
verificate 84 risorse operative incluse, senza cartelle output, `.env` o cache degli
script. Controllate visivamente le schermate Qt generate. La build di verifica è
in `build/verification-dist/MyWayTools`; non è un installer di release e non include
la copia separata di `_runtime` effettuata dal normale `build.bat`.
