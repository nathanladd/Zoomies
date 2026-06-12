<#
.SYNOPSIS
    Build the Zoomies Windows installer end-to-end.

.DESCRIPTION
    1. Reads __version__ from version.py.
    2. Cleans previous dist/ and build/ output.
    3. Runs PyInstaller against Zoomies.spec to produce dist\Zoomies\.
    4. Invokes Inno Setup (ISCC.exe) to produce dist\installer\Zoomies-Setup-<version>.exe.

.PARAMETER SkipPyInstaller
    Skip the PyInstaller step (useful when iterating on the .iss only).

.PARAMETER SkipInstaller
    Skip the Inno Setup step (produces just the PyInstaller bundle).

.EXAMPLE
    .\build.ps1

.EXAMPLE
    .\build.ps1 -SkipInstaller    # just build the exe bundle

.NOTES
    Requirements:
      - Python venv with `pyinstaller` and all runtime deps installed.
      - Inno Setup 6 on PATH, or at the default install location.
#>
[CmdletBinding()]
param(
    [switch]$SkipPyInstaller,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath
Set-Location $ProjectRoot

# ---- Read version -----------------------------------------------------------
$versionPy = Join-Path $ProjectRoot "version.py"
if (-not (Test-Path $versionPy)) { throw "version.py not found at $versionPy" }
$match = Select-String -Path $versionPy -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $match) { throw "Could not parse __version__ from version.py" }
$AppVersion = $match.Matches[0].Groups[1].Value
Write-Host "[build] App version: $AppVersion" -ForegroundColor Cyan

# ---- Locate Python ----------------------------------------------------------
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Warning "[.venv\Scripts\python.exe not found, falling back to 'python' on PATH"
    $PythonExe = "python"
}
Write-Host "[build] Python: $PythonExe" -ForegroundColor Cyan

# ---- PyInstaller ------------------------------------------------------------
if (-not $SkipPyInstaller) {
    Write-Host "[build] Cleaning previous PyInstaller output..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$ProjectRoot\build"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$ProjectRoot\dist\Zoomies"

    Write-Host "[build] Running PyInstaller..." -ForegroundColor Cyan
    & $PythonExe -m PyInstaller "Zoomies.spec" --noconfirm --clean
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

    $bundleExe = Join-Path $ProjectRoot "dist\Zoomies\Zoomies.exe"
    if (-not (Test-Path $bundleExe)) { throw "PyInstaller did not produce $bundleExe" }
    Write-Host "[build] PyInstaller bundle ready: $bundleExe" -ForegroundColor Green
} else {
    Write-Host "[build] Skipping PyInstaller (per -SkipPyInstaller)" -ForegroundColor Yellow
}

# ---- Inno Setup -------------------------------------------------------------
if (-not $SkipInstaller) {
    $iscc = $null
    foreach ($candidate in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "ISCC.exe"
    )) {
        if ($candidate -eq "ISCC.exe") {
            $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
            if ($cmd) { $iscc = $cmd.Source; break }
        } elseif (Test-Path $candidate) {
            $iscc = $candidate; break
        }
    }
    if (-not $iscc) {
        throw "Inno Setup compiler (ISCC.exe) not found. Install Inno Setup 6 from https://jrsoftware.org/isinfo.php and re-run."
    }
    Write-Host "[build] Using Inno Setup: $iscc" -ForegroundColor Cyan

    New-Item -ItemType Directory -Force -Path "$ProjectRoot\dist\installer" | Out-Null

    & $iscc "/DAppVersion=$AppVersion" (Join-Path $ProjectRoot "installer\Zoomies.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed with exit code $LASTEXITCODE" }

    $installer = Join-Path $ProjectRoot "dist\installer\Zoomies-Setup-$AppVersion.exe"
    if (Test-Path $installer) {
        Write-Host "[build] Installer ready: $installer" -ForegroundColor Green
    } else {
        Write-Warning "Installer script completed but $installer was not found."
    }
} else {
    Write-Host "[build] Skipping Inno Setup (per -SkipInstaller)" -ForegroundColor Yellow
}

Write-Host "[build] Done." -ForegroundColor Green
