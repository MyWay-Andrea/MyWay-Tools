[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Origine
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSCommandPath
$destinazione = Join-Path $repoRoot "scripts"
$origineRisolta = (Resolve-Path -LiteralPath $Origine).Path
$destinazioneRisolta = (Resolve-Path -LiteralPath $destinazione).Path

if ($origineRisolta -eq $destinazioneRisolta) {
    throw "La cartella di origine non puo' coincidere con scripts del repository."
}

$cartelle = @(
    "BUSINESS\common",
    "BUSINESS\config",
    "BUSINESS\02_(OLD)_APPUNTAMENTI_SETTIMANA",
    "BUSINESS\09_ESTRAZIONE_ORDINI_API",
    "BUSINESS\10_ESTRAZIONE_OPP_API",
    "BUSINESS\11_ESTRAZIONE_APP_API",
    "BUSINESS\12_FCST_BUSINESS",
    "BUSINESS\13_ESTRAI_FILE_GARA",
    "BUSINESS\14_ELABORA_CB",
    "BUSINESS\CAMPAGNE",
    "CONSUMER\common",
    "CONSUMER\config",
    "CONSUMER\01_FORMATTA_PEDONALITA",
    "CONSUMER\02_REPORT_PEDONALITA",
    "CONSUMER\03_FORMATTA_MAGAZZINO",
    "CONSUMER\11_CRUSCOTTO_AGGREGATIVO",
    "CONSUMER\12_CRUSCOTTO_PISTA_CONSUMER",
    "CONSUMER\13_REPORT_GIACENZE"
)

$fileCondivisi = @(
    "config_env.py",
    "graph_sharepoint.py"
)

function Remove-File-Locali {
    param([Parameter(Mandatory = $true)][string]$Radice)

    $directoryEscluse = @(
        ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
        ".ruff_cache", ".tox", ".nox", ".venv", "venv", "env", "node_modules",
        "build", "dist"
    )
    $fileLocaleRegex = '^(?:\.env(?:\..*)?|.*\.(?:pem|key|pfx|p12|p8|kdbx|pyc|pyo|tmp|bak|swp)|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?|(?:credentials?|secrets?|tokens?)(?:\..*)?|thumbs\.db|\.ds_store)$'

    $directoryDaEliminare = Get-ChildItem -LiteralPath $Radice -Directory -Recurse -Force |
        Where-Object { $directoryEscluse -contains $_.Name.ToLowerInvariant() } |
        Sort-Object { $_.FullName.Length } -Descending

    foreach ($directory in $directoryDaEliminare) {
        Remove-Item -LiteralPath $directory.FullName -Recurse -Force
    }

    $fileDaEliminare = Get-ChildItem -LiteralPath $Radice -File -Recurse -Force |
        Where-Object { $_.Name -match $fileLocaleRegex }

    foreach ($file in $fileDaEliminare) {
        Remove-Item -LiteralPath $file.FullName -Force
    }
}

$mancanti = @()
foreach ($elemento in @($cartelle + $fileCondivisi)) {
    if (-not (Test-Path -LiteralPath (Join-Path $origineRisolta $elemento))) {
        $mancanti += $elemento
    }
}
if ($mancanti.Count -gt 0) {
    throw "Origine incompleta. Elementi mancanti:`n - $($mancanti -join "`n - ")"
}

$temporanea = Join-Path $repoRoot ".scripts_sync_tmp"
if (Test-Path -LiteralPath $temporanea) {
    Remove-Item -LiteralPath $temporanea -Recurse -Force
}
New-Item -ItemType Directory -Path $temporanea | Out-Null

try {
    foreach ($cartella in $cartelle) {
        $sorgente = Join-Path $origineRisolta $cartella
        $target = Join-Path $temporanea $cartella
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $sorgente -Destination $target -Recurse -Force
    }
    foreach ($file in $fileCondivisi) {
        Copy-Item -LiteralPath (Join-Path $origineRisolta $file) -Destination (Join-Path $temporanea $file) -Force
    }

    # File di test/documentazione che non vengono eseguiti dal menu.
    @(
        "BUSINESS\09_ESTRAZIONE_ORDINI_API\prove",
        "BUSINESS\10_ESTRAZIONE_OPP_API\prova.py",
        "BUSINESS\14_ELABORA_CB\estrai_anagrafica_crm_json.py",
        "BUSINESS\14_ELABORA_CB\ISTRUZIONI_EXCHANGE_APP_RBAC_REPORTISTICA.html",
        "CONSUMER\02_REPORT_PEDONALITA\script\calcolaW-n.py"
    ) | ForEach-Object {
        $elemento = Join-Path $temporanea $_
        if (Test-Path -LiteralPath $elemento) {
            Remove-Item -LiteralPath $elemento -Recurse -Force
        }
    }

    # Rimuove ricorsivamente credenziali, cache e artefatti locali dalle cartelle
    # selezionate prima che arrivino nel repository o nell'installer.
    Remove-File-Locali -Radice $temporanea

    Get-ChildItem -LiteralPath $destinazioneRisolta -Force |
        Where-Object { $_.Name -ne ".env" } |
        Remove-Item -Recurse -Force
    Copy-Item -Path (Join-Path $temporanea "*") -Destination $destinazioneRisolta -Recurse -Force
}
finally {
    if (Test-Path -LiteralPath $temporanea) {
        Remove-Item -LiteralPath $temporanea -Recurse -Force
    }
}

Write-Host "Cartella scripts aggiornata con i soli progetti usati dal menu."
Write-Host "Credenziali, cache e file locali sono stati esclusi ricorsivamente."
Write-Host "Il file locale scripts\.env, se presente, e' stato conservato ma non sara' incluso nell'installer."
