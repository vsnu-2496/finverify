# Find Ollama installation
Write-Output "=== Searching for ollama.exe ==="

# Check common paths
$paths = @(
    "C:\Users\vishn\AppData\Local\Programs\Ollama\ollama.exe",
    "C:\Program Files\Ollama\ollama.exe",
    "C:\Program Files (x86)\Ollama\ollama.exe",
    "C:\Users\vishn\Ollama\ollama.exe",
    "C:\Users\vishn\AppData\Local\Ollama\ollama.exe"
)

foreach ($p in $paths) {
    if (Test-Path $p) {
        Write-Output "FOUND: $p"
    }
}

# Check PATH
$envPath = $env:PATH -split ';'
foreach ($dir in $envPath) {
    $candidate = Join-Path $dir "ollama.exe"
    if (Test-Path $candidate) {
        Write-Output "FOUND ON PATH: $candidate"
    }
}

# Check registry for install location
$regPaths = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*"
)

foreach ($regPath in $regPaths) {
    $items = Get-ItemProperty $regPath -ErrorAction SilentlyContinue
    foreach ($item in $items) {
        if ($item.DisplayName -like '*Ollama*') {
            Write-Output "REGISTRY: $($item.DisplayName) at $($item.InstallLocation) v$($item.DisplayVersion)"
        }
    }
}

# Quick search of user profile
$found = Get-ChildItem -Path "C:\Users\vishn" -Filter "ollama.exe" -Recurse -ErrorAction SilentlyContinue -Depth 4
foreach ($f in $found) {
    Write-Output "FOUND IN PROFILE: $($f.FullName)"
}

Write-Output "=== Search complete ==="
