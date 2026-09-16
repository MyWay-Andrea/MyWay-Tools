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

* Gli script operativi presenti in `scripts/` sono inclusi nella build.
* SharePoint continua a contenere input, output e file `.env`; questi ultimi non vengono copiati nella repository.
* Le modifiche a `menu.py`, agli script, `updater.py`, `Menu.spec`, `setup.iss`, `requirements_runtime.txt` o `version.txt` richiedono una nuova build e una nuova release.
* L'installer richiede privilegi amministrativi per installare in `Program Files`.
