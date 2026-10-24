#Requires -Version 5.1
<#
.SYNOPSIS
    Build the lolping Windows release (one-folder exe + zip).

.DESCRIPTION
    Creates a private build virtual environment (.venv-build), installs the
    runtime and build dependencies there, runs the test suite, packages the
    application with PyInstaller, verifies the frozen executable, copies the
    user-facing documents next to the exe and produces the release zip with a
    SHA256 checksum.

    No administrator rights are required and nothing is installed into the
    system Python.  Everything this script creates is ignored by git, or at
    least should be: dist\, build\_work\, release\, .venv-build\.

.PARAMETER PythonExe
    Interpreter used to create the build virtual environment.  Defaults to
    "python" from PATH.  Point it at a specific interpreter to work around a
    PyInstaller / Python version mismatch:
        .\build\build.ps1 -PythonExe "C:\Python312\python.exe" -Clean

.PARAMETER Clean
    Delete previous build output (dist\, build\_work\ and the release zip)
    before starting.  The virtual environment is kept so rebuilds stay fast.

.PARAMETER SkipTests
    Do not run pytest and do not run the frozen --self-test sanity check.
    The build becomes faster but is no longer verified; use only when
    iterating on packaging itself.

.EXAMPLE
    .\build\build.ps1

.EXAMPLE
    .\build\build.ps1 -Clean -PythonExe "C:\Python312\python.exe"

.NOTES
    See docs/07-build-and-release.md for the full release checklist.
#>
[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [switch]$Clean,
    [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
$Root = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $Root ".venv-build"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$SrcPackage = Join-Path $Root "src\lolping"
$EntryPoint = Join-Path $SrcPackage "__main__.py"
$InitFile = Join-Path $SrcPackage "__init__.py"
$SpecFile = Join-Path $Root "build\lolping.spec"
$DistDir = Join-Path $Root "dist"
$WorkDir = Join-Path $Root "build\_work"
$ReleaseDir = Join-Path $Root "release"
$AppName = "lolping"

$script:ExitCode = 0

# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
function Write-Step {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked {
    <# Run a native command, fail loudly if it returns a non-zero exit code. #>
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$Step
    )
    Write-Host "    > $FilePath $($Arguments -join ' ')" -ForegroundColor DarkGray
    & $FilePath @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$Step failed (exit code $exitCode)."
    }
}

function Get-ProjectVersion {
    <# Read __version__ from src\lolping\__init__.py, fall back to 0.2.0. #>
    param([Parameter(Mandatory)][string]$InitFile)
    if (Test-Path -LiteralPath $InitFile) {
        $match = Select-String -LiteralPath $InitFile `
            -Pattern '__version__\s*=\s*["'']([0-9]+\.[0-9]+\.[0-9]+)["'']' |
            Select-Object -First 1
        if ($null -ne $match) {
            return $match.Matches[0].Groups[1].Value
        }
    }
    Write-Warning "Could not read __version__ from $InitFile; assuming 0.2.0."
    return "0.2.0"
}

function Get-PythonFacts {
    <# Return the interpreter version and architecture as a small object. #>
    param([Parameter(Mandatory)][string]$Exe)
    $raw = & $Exe -c "import sys, platform; print('%d.%d.%d|%s' % (sys.version_info[0], sys.version_info[1], sys.version_info[2], platform.architecture()[0]))"
    if ($LASTEXITCODE -ne 0) {
        throw "The interpreter '$Exe' could not be executed."
    }
    $line = @($raw)[0]
    if ([string]::IsNullOrWhiteSpace($line)) {
        throw "The interpreter '$Exe' returned no version information."
    }
    $parts = $line.ToString().Trim().Split("|")
    return [pscustomobject]@{
        Version = $parts[0]
        Arch    = $parts[1]
        Major   = [int]($parts[0].Split(".")[0])
        Minor   = [int]($parts[0].Split(".")[1])
    }
}

function Get-FileSizeText {
    param([Parameter(Mandatory)][string]$Path)
    $bytes = (Get-Item -LiteralPath $Path).Length
    if ($bytes -ge 1MB) {
        return ("{0:N1} MB" -f ($bytes / 1MB))
    }
    return ("{0:N0} KB" -f ($bytes / 1KB))
}

# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
try {
    Write-Host "lolping release build" -ForegroundColor White
    Write-Host "  repository : $Root"
    Write-Host "  interpreter: $PythonExe"

    # -- sanity checks -----------------------------------------------------
    foreach ($required in @($EntryPoint, $SpecFile, (Join-Path $Root "requirements.txt"), (Join-Path $Root "requirements-dev.txt"))) {
        if (-not (Test-Path -LiteralPath $required)) {
            throw "Required file is missing: $required`nRun the script from a complete checkout of the repository."
        }
    }

    $facts = Get-PythonFacts -Exe $PythonExe
    Write-Host "  python     : $($facts.Version) ($($facts.Arch))"

    if ($facts.Arch -ne "64bit") {
        throw "A 64-bit Python interpreter is required for the win64 release (found $($facts.Arch)). Install 64-bit Python 3.12/3.14 and re-run with -PythonExe <path>."
    }

    if ($facts.Minor -ge 14) {
        Write-Warning ("Python {0} is very new. PyInstaller support for new CPython releases can lag behind, and the PyQt5 wheels are old. If the dependency install or the PyInstaller step fails, rebuild with Python 3.12 instead: .\build\build.ps1 -PythonExe 'C:\Python312\python.exe' -Clean" -f $facts.Version)
    }

    $version = Get-ProjectVersion -InitFile $InitFile
    $zipPath = Join-Path $ReleaseDir "$AppName-$version-win64.zip"
    Write-Host "  version    : $version"
    Write-Host "  output     : $zipPath"

    # -- optional clean ----------------------------------------------------
    if ($Clean) {
        Write-Step "Cleaning previous build output"
        foreach ($path in @($DistDir, $WorkDir)) {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Recurse -Force
                Write-Host "    removed $path"
            }
        }
        foreach ($stale in @($zipPath, "$zipPath.sha256")) {
            if (Test-Path -LiteralPath $stale) {
                Remove-Item -LiteralPath $stale -Force
                Write-Host "    removed $stale"
            }
        }
    }

    # -- build virtual environment ----------------------------------------
    Write-Step "Preparing build virtual environment (.venv-build)"
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        if (Test-Path -LiteralPath $VenvDir) {
            Write-Host "    removing incomplete virtual environment"
            Remove-Item -LiteralPath $VenvDir -Recurse -Force
        }
        Invoke-Checked -FilePath $PythonExe -Arguments @("-m", "venv", $VenvDir) -Step "Creating the build virtual environment"
    }
    else {
        Write-Host "    reusing existing $VenvDir"
    }

    Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "pip") -Step "Upgrading pip"

    $runtimeReqs = Join-Path $Root "requirements.txt"
    $devReqs = Join-Path $Root "requirements-dev.txt"
    Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "--disable-pip-version-check", "-r", $runtimeReqs, "-r", $devReqs) -Step "Installing dependencies"

    # -- tests -------------------------------------------------------------
    $ranPytest = $false
    $ranFrozenCheck = $false
    if ($SkipTests) {
        Write-Step "Skipping tests (-SkipTests)"
    }
    else {
        Write-Step "Running the test suite"
        $testsDir = Join-Path $Root "tests"
        if (Test-Path -LiteralPath $testsDir) {
            $previousPythonPath = $env:PYTHONPATH
            $env:PYTHONPATH = Join-Path $Root "src"
            try {
                Push-Location -LiteralPath $Root
                try {
                    Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pytest", "-q") -Step "pytest"
                    $ranPytest = $true
                }
                finally {
                    Pop-Location
                }
            }
            finally {
                if ($null -eq $previousPythonPath) {
                    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
                }
                else {
                    $env:PYTHONPATH = $previousPythonPath
                }
            }
        }
        else {
            Write-Warning "tests\ does not exist yet; skipping pytest (the release checklist in docs/07-build-and-release.md requires it)."
        }
    }

    # -- PyInstaller -------------------------------------------------------
    Write-Step "Building the executable with PyInstaller"
    Push-Location -LiteralPath $Root
    try {
        Invoke-Checked -FilePath $VenvPython `
            -Arguments @("-m", "PyInstaller", "--noconfirm", "--distpath", $DistDir, "--workpath", $WorkDir, $SpecFile) `
            -Step "PyInstaller build"
    }
    finally {
        Pop-Location
    }

    $appDir = Join-Path $DistDir $AppName
    $exePath = Join-Path $appDir "$AppName.exe"
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "The build finished but the expected executable is missing: $exePath"
    }

    # -- documents next to the exe ----------------------------------------
    Write-Step "Adding user-facing documents to the distribution folder"
    $readme = Join-Path $Root "README.md"
    if (Test-Path -LiteralPath $readme) {
        Copy-Item -LiteralPath $readme -Destination $appDir -Force
        Write-Host "    copied README.md"
    }
    else {
        Write-Warning "README.md not found; the release zip will not contain it."
    }
    $license = Join-Path $Root "LICENSE"
    if (Test-Path -LiteralPath $license) {
        Copy-Item -LiteralPath $license -Destination $appDir -Force
        Write-Host "    copied LICENSE"
    }
    else {
        Write-Host "    no LICENSE file in the repository; skipped (add one before publishing)."
    }

    # -- frozen smoke test -------------------------------------------------
    if (-not $SkipTests) {
        Write-Step "Verifying the frozen executable (offscreen --self-test)"
        $env:QT_QPA_PLATFORM = "offscreen"
        try {
            $process = Start-Process -FilePath $exePath -ArgumentList "--self-test" -PassThru -WindowStyle Hidden
            if (-not $process.WaitForExit(120000)) {
                try { $process.Kill() } catch { }
                throw "The frozen exe did not finish '--self-test' within 120 seconds (it may be stuck on a modal error dialog)."
            }
            if ($process.ExitCode -ne 0) {
                throw "The frozen exe failed '--self-test' with exit code $($process.ExitCode). Run it manually with QT_QPA_PLATFORM=offscreen to see the traceback."
            }
            Write-Host "    frozen self-test OK (exit code 0)"
            $ranFrozenCheck = $true
        }
        finally {
            Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        }
    }

    # -- release zip + checksum -------------------------------------------
    Write-Step "Creating the release archive"
    New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -LiteralPath $appDir -DestinationPath $zipPath -CompressionLevel Optimal
    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $shaFile = "$zipPath.sha256"
    Set-Content -LiteralPath $shaFile -Value "$hash  $([System.IO.Path]::GetFileName($zipPath))" -Encoding ASCII

    $zipSize = Get-FileSizeText -Path $zipPath
    $exeSize = Get-FileSizeText -Path $exePath

    if ($SkipTests) {
        $testSummary = "skipped (-SkipTests)"
    }
    elseif ($ranPytest -and $ranFrozenCheck) {
        $testSummary = "pytest + frozen self-test passed"
    }
    elseif ($ranPytest) {
        $testSummary = "pytest passed; frozen self-test skipped"
    }
    else {
        $testSummary = "pytest skipped (tests\ missing); frozen self-test passed"
    }

    Write-Host ""
    Write-Host "Build succeeded." -ForegroundColor Green
    Write-Host "  exe        : $exePath ($exeSize)"
    Write-Host "  release zip: $zipPath ($zipSize)"
    Write-Host "  sha256     : $hash"
    Write-Host "  tests      : $testSummary"
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Unzip $([System.IO.Path]::GetFileName($zipPath)) into an empty folder on a clean Windows VM."
    Write-Host "  2. Run lolping\lolping.exe and try the wheel, the tray menu and Settings."
    Write-Host "  3. Follow the release checklist in docs/07-build-and-release.md before tagging v$version."
}
catch {
    Write-Host ""
    Write-Host "BUILD FAILED" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    $script:ExitCode = 1
}

exit $script:ExitCode
