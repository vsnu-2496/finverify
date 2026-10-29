# Download and extract portable Ollama for Windows
$ollamaDir = "C:\Users\vishn\Ollama"
$zipUrl = "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip"
$zipFile = Join-Path $ollamaDir "ollama-windows-amd64.zip"

# Create directory
New-Item -ItemType Directory -Path $ollamaDir -Force | Out-Null

Write-Output "Downloading Ollama portable ZIP..."
Write-Output "URL: $zipUrl"
Write-Output "Target: $zipFile"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing

Write-Output "Download complete. Size: $([math]::Round((Get-Item $zipFile).Length / 1MB, 1)) MB"

Write-Output "Extracting..."
Expand-Archive -Path $zipFile -DestinationPath $ollamaDir -Force

Write-Output "Contents:"
Get-ChildItem $ollamaDir -Recurse | Select-Object FullName

# Verify ollama.exe exists
$ollamaExe = Join-Path $ollamaDir "ollama.exe"
if (Test-Path $ollamaExe) {
    Write-Output ""
    Write-Output "SUCCESS: ollama.exe found at $ollamaExe"
    $version = & $ollamaExe --version 2>&1
    Write-Output "VERSION: $version"
} else {
    Write-Output "ERROR: ollama.exe not found after extraction"
}
