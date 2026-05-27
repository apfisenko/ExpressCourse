param(
    [Parameter(Position = 0)]
    [string]$Command = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

function Initialize-ToolPath {
    $paths = @(
        (Join-Path $env:USERPROFILE "scoop\shims"),
        (Join-Path $env:USERPROFILE "scoop\apps\ffmpeg\current\bin")
    )
    foreach ($path in $paths) {
        if ((Test-Path -LiteralPath $path) -and ($env:Path -notlike "*$path*")) {
            $env:Path = "$path;$env:Path"
        }
    }
}

Initialize-ToolPath

function Get-WslProjectRoot {
    $resolved = (Resolve-Path -LiteralPath $ProjectRoot).Path

    if ($resolved -match '^([A-Za-z]):\\(.*)$') {
        $drive = $Matches[1].ToLower()
        $rest = $Matches[2] -replace '\\', '/'
        return "/mnt/$drive/$rest"
    }

    throw "Failed to convert path to WSL: $resolved"
}

function Stop-BotInstances {
    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    $venvPythonUnix = Join-Path $ProjectRoot ".venv/bin/python"
    $stopped = $false

    $targets = Get-CimInstance Win32_Process | Where-Object {
        if (-not $_.CommandLine) { return $false }

        if ($_.CommandLine -match 'main\.py') {
            if ($_.ExecutablePath -eq $venvPython -or $_.ExecutablePath -eq $venvPythonUnix) {
                return $true
            }
            if ($_.CommandLine -like "*$ProjectRoot*main.py*") {
                return $true
            }
        }

        if ($_.Name -eq 'uv.exe' -and $_.CommandLine -match 'run python main\.py') {
            $childPython = Get-CimInstance Win32_Process | Where-Object {
                $_.CommandLine -match 'main\.py' -and (
                    $_.ExecutablePath -eq $venvPython -or
                    $_.ExecutablePath -eq $venvPythonUnix
                )
            }
            if ($childPython) { return $true }
        }

        return $false
    }

    if ($targets) {
        Write-Host "Stopping existing bot instance(s)..."
        $targets | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
        $stopped = $true
    }

    if ($stopped) {
        Start-Sleep -Seconds 1
    }
}

Push-Location $ProjectRoot
try {
    switch ($Command) {
        "install" {
            uv sync
        }
        "stop" {
            Stop-BotInstances
        }
        "run" {
            Stop-BotInstances
            uv run python main.py
        }
        "docker-run" {
            Stop-BotInstances
            $wslRoot = Get-WslProjectRoot
            & wsl.exe bash -lc "cd '$wslRoot' && bash make.sh docker-run"
        }
        "rag-index" {
            uv run python rag_cli.py
        }
        "rag-reindex" {
            uv run python rag_cli.py --reindex
        }
        default {
            Write-Host "Usage: .\make.ps1 {install|stop|run|docker-run|rag-index|rag-reindex}"
            exit 1
        }
    }
}
finally {
    Pop-Location
}
