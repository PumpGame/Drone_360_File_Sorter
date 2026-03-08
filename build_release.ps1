Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "== Drone360FileSorter: build release =="

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $PY = $venvPython
    Write-Host "Using Python from venv: $PY"
} else {
    $PY = "python"
    Write-Host "Using Python from PATH: $PY"
}

Write-Host "Upgrading pip..."
& $PY -m pip install -U pip

Write-Host "Ensuring PyInstaller is installed..."
& $PY -m pip install pyinstaller

foreach ($dir in @("build", "dist")) {
    $fullPath = Join-Path $repoRoot $dir
    if (Test-Path $fullPath) {
        Write-Host "Removing old $dir..."
        try {
            Remove-Item -Path $fullPath -Recurse -Force
        } catch {
            throw "Failed to remove '$fullPath': $($_.Exception.Message)"
        }
    }
}

$iconPath = "C:\Users\klaud\Repos\Drone_360_File_Sorter\icon.ico"
if (-not (Test-Path $iconPath)) {
    throw "Icon not found: $iconPath"
}

Write-Host "Building onefile EXE with PyInstaller..."
& $PY -m PyInstaller --onefile --windowed --name "Drone360FileSorter" --icon $iconPath --add-data "$iconPath;." main.py

$releaseDir = Join-Path $repoRoot "release"
if (-not (Test-Path $releaseDir)) {
    Write-Host "Creating release directory..."
    New-Item -Path $releaseDir -ItemType Directory | Out-Null
}

$versionFile = Join-Path $repoRoot "VERSION"
if (Test-Path $versionFile) {
    $version = (Get-Content -Path $versionFile -Raw).Trim()
    if (-not $version) {
        $version = Get-Date -Format "yyyyMMdd_HHmm"
    }
} else {
    $version = Get-Date -Format "yyyyMMdd_HHmm"
}

$builtExe = Join-Path $repoRoot "dist\Drone360FileSorter.exe"
if (-not (Test-Path $builtExe)) {
    throw "Build output not found: $builtExe"
}

$releaseExeName = "Drone360FileSorter_{0}.exe" -f $version
$releaseExePath = Join-Path $releaseDir $releaseExeName

Write-Host "Copying EXE to release..."
Copy-Item -Path $builtExe -Destination $releaseExePath -Force

$zipName = "Drone360FileSorter_{0}_win64.zip" -f $version
$zipPath = Join-Path $releaseDir $zipName
if (Test-Path $zipPath) {
    Remove-Item -Path $zipPath -Force
}

Write-Host "Creating ZIP package..."
Compress-Archive -Path $releaseExePath -DestinationPath $zipPath -Force

$hash = Get-FileHash -Path $zipPath -Algorithm SHA256
$shaName = "Drone360FileSorter_{0}_win64_SHA256.txt" -f $version
$shaPath = Join-Path $releaseDir $shaName
$shaContent = "{0}  {1}" -f $hash.Hash, (Split-Path $zipPath -Leaf)
Set-Content -Path $shaPath -Value $shaContent -Encoding ASCII

Write-Host ""
Write-Host "Build completed successfully."
Write-Host "EXE: $releaseExePath"
Write-Host "ZIP: $zipPath"
Write-Host "SHA256: $shaPath"

exit 0
