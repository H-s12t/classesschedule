param(
    [string]$Python = "",
    [string]$OutputDir = "dist\portable"
)

$ErrorActionPreference = "Stop"
$projectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$srcMain = Join-Path $projectDir "src\main.py"
$distDir = Join-Path $projectDir $OutputDir
$pyprojectPath = Join-Path $projectDir "pyproject.toml"
$configPath = Join-Path $projectDir "src\core\config.py"

if (-not (Test-Path $srcMain)) {
    throw "Application entry point not found: $srcMain"
}

if (-not (Test-Path $pyprojectPath)) {
    throw "Project metadata not found: $pyprojectPath"
}

if (-not (Test-Path $configPath)) {
    throw "Application config not found: $configPath"
}

$pyprojectText = Get-Content $pyprojectPath -Raw -Encoding UTF8
$configText = Get-Content $configPath -Raw -Encoding UTF8

$buildVersionMatch = [regex]::Match($pyprojectText, '(?m)^\s*build_version\s*=\s*"([^"]+)"\s*$')
$buildNumberMatch = [regex]::Match($pyprojectText, '(?m)^\s*build_number\s*=\s*(\d+)\s*$')
$appVersionMatch = [regex]::Match($configText, '(?m)^\s*APP_VERSION\s*=\s*"([^"]+)"\s*$')
$appBuildMatch = [regex]::Match($configText, '(?m)^\s*APP_BUILD\s*=\s*(\d+)\s*$')

if (-not ($buildVersionMatch.Success -and $buildNumberMatch.Success -and $appVersionMatch.Success -and $appBuildMatch.Success)) {
    throw "Failed to read synchronized version metadata from pyproject.toml and src/core/config.py"
}

$buildVersion = $buildVersionMatch.Groups[1].Value
$buildNumber = [int]$buildNumberMatch.Groups[1].Value
$appVersion = $appVersionMatch.Groups[1].Value
$appBuild = [int]$appBuildMatch.Groups[1].Value

if ($buildVersion -ne $appVersion -or $buildNumber -ne $appBuild) {
    throw "Version metadata mismatch between pyproject.toml ([tool.flet] build_version/build_number) and src/core/config.py (APP_VERSION/APP_BUILD)"
}

$productVersion = $buildVersion
$fileVersion = "$buildVersion.$buildNumber"

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
        --product-version $productVersion `
        --file-version $fileVersion `
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