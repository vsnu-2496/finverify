# Read the updated user PATH from registry (not current process PATH)
$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
$machinePath = [Environment]::GetEnvironmentVariable('PATH', 'Machine')
$fullPath = "$machinePath;$userPath"

Write-Output "=== Checking updated PATH for Ollama ==="
$dirs = $fullPath -split ';'
foreach ($dir in $dirs) {
    if ($dir -and (Test-Path (Join-Path $dir "ollama.exe") -ErrorAction SilentlyContinue)) {
        Write-Output "FOUND: $(Join-Path $dir 'ollama.exe')"
    }
}

# Try running ollama with updated PATH
$env:PATH = $fullPath
try {
    $version = & ollama --version 2>&1
    Write-Output "VERSION: $version"
} catch {
    Write-Output "OLLAMA NOT RUNNABLE"
}

# Also do a broader search
$searchDirs = @(
    "C:\Users\vishn\AppData\Local",
    "C:\Users\vishn\AppData\Roaming", 
    "C:\ProgramData"
)
foreach ($sd in $searchDirs) {
    if (Test-Path $sd) {
        $found = Get-ChildItem -Path $sd -Filter "ollama.exe" -Recurse -ErrorAction SilentlyContinue -Depth 3
        foreach ($f in $found) {
            Write-Output "DEEP SEARCH FOUND: $($f.FullName)"
        }
    }
}

Write-Output "=== Done ==="
