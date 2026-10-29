$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor
$gpu = Get-CimInstance Win32_VideoController

Write-Output "=== SYSTEM SPECS ==="
Write-Output ("Total RAM (GB): " + [math]::Round($cs.TotalPhysicalMemory/1GB, 1))
Write-Output ("Free RAM (GB): " + [math]::Round($os.FreePhysicalMemory/1MB, 1))
Write-Output ("CPU: " + $cpu.Name)
Write-Output ("CPU Cores: " + $cpu.NumberOfCores)
Write-Output ("CPU Threads: " + $cpu.NumberOfLogicalProcessors)
Write-Output ("GPU: " + $gpu.Name)
Write-Output ("GPU VRAM (bytes): " + $gpu.AdapterRAM)
Write-Output ("GPU VRAM (GB): " + [math]::Round($gpu.AdapterRAM/1GB, 1))

# Disk space
Get-PSDrive -PSProvider FileSystem | ForEach-Object {
    $total = $_.Used + $_.Free
    if ($total -gt 0) {
        Write-Output ("Drive " + $_.Name + ": Used=" + [math]::Round($_.Used/1GB,1) + "GB Free=" + [math]::Round($_.Free/1GB,1) + "GB Total=" + [math]::Round($total/1GB,1) + "GB")
    }
}

# Ollama check
Write-Output ""
$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaPath) {
    Write-Output ("Ollama: INSTALLED at " + $ollamaPath.Source)
    ollama list 2>&1
} else {
    Write-Output "Ollama: NOT INSTALLED"
}

# Check for other local LLM tools
Write-Output ""
$lmstudio = Get-Command lms -ErrorAction SilentlyContinue
if ($lmstudio) { Write-Output "LM Studio CLI: FOUND" } else { Write-Output "LM Studio CLI: NOT FOUND" }

$llamacpp = Get-Command llama-cli -ErrorAction SilentlyContinue
if ($llamacpp) { Write-Output "llama.cpp: FOUND" } else { Write-Output "llama.cpp: NOT FOUND" }
