param(
    [string]$Python = "",
    [string]$OutputDir = "dist\portable"
)

$ErrorActionPreference = "Stop"
$projectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$srcMain = Join-Path $projectDir "src\main.py"
$distDir = Join-Path $projectDir $OutputDir

if (-not (Test-Path $srcMain)) {
    throw "Application entry point not found: $srcMain"
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    $localPython = Join-Path $projectDir ".venv\Scripts\python.exe"
    if (Test-Path $localPython) {
        $Python = $localPython
    } else {
        $Python = (Get-Command python -ErrorAction Stop).Source
    }
}

$fletExe = Join-Path ([System.IO.Path]::GetDirectoryName($Python)) "flet.exe"
if (-not (Test-Path $fletExe)) {
    throw "Flet CLI not found: $fletExe. Install flet and flet-cli in this Python environment."
}

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
Write-Host "Project: $projectDir"
Write-Host "Python: $Python"
Write-Host "Output: $distDir"

Push-Location $projectDir
try {
    & $fletExe pack $srcMain `
        --onedir `
        --name "class_schedule" `
        --distpath $distDir `
        --product-name "Class Schedule" `
        --file-description "Class Schedule" `
        --product-version "0.1.0" `
        --file-version "0.1.0.0" `
        --yes `
        --no-rich-output
    if ($LASTEXITCODE -ne 0) {
        throw "Flet portable build failed with exit code: $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$portableDir = Join-Path $distDir "class_schedule"
$exePath = Join-Path $portableDir "class_schedule.exe"
if (-not (Test-Path $exePath)) {
    throw "Build completed but output was not found: $exePath"
}

Write-Host ""
Write-Host "Portable package: $portableDir"
Write-Host "Run: $exePath"