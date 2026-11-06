$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Build this Windows executable on Windows 10/11.' }
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot
try {
    $Venv = Join-Path $PSScriptRoot '.build-venv'
    if (-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) {
        & py -3 -m venv $Venv
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.10+ with Tkinter from python.org.' }
    }
    $Python = Join-Path $Venv 'Scripts\python.exe'
    & $Python -c 'import sys, tkinter; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ with Tkinter is required.' }
    & $Python -m pip install --disable-pip-version-check -r windows/requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
    & $Python -m unittest discover -s windows -p test_desktop.py -v
    if ($LASTEXITCODE -ne 0) { throw 'Desktop database tests failed.' }
    & $Python windows/desktop.py --smoke-test
    if ($LASTEXITCODE -ne 0) { throw 'Source application smoke test failed.' }
    & $Python -m PyInstaller --clean --noconfirm --distpath windows/dist --workpath windows/build windows/NexvantEngineering.spec
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
    $Executable = Join-Path $PSScriptRoot 'dist\NexvantEngineering.exe'
    $Process = Start-Process -FilePath $Executable -ArgumentList '--smoke-test' -Wait -PassThru
    if ($Process.ExitCode -ne 0) { throw "Packaged application smoke test failed: $($Process.ExitCode)" }
    Write-Host "Built and smoke-tested: $Executable"
    Write-Host 'Distribute the executable after testing on the target Windows PC. It is not code-signed.'
} finally {
    Pop-Location
}
