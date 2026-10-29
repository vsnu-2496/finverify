"""Download portable Ollama ZIP with retry support using urllib (no extra deps)."""
import hashlib
import os
import shutil
import sys
import time
import urllib.request
import zipfile

OLLAMA_DIR = r"C:\Users\vishn\Ollama"
ZIP_PATH = os.path.join(OLLAMA_DIR, "ollama-windows-amd64.zip")
URL = "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip"
MAX_RETRIES = 3

os.makedirs(OLLAMA_DIR, exist_ok=True)

for attempt in range(1, MAX_RETRIES + 1):
    print(f"Download attempt {attempt}/{MAX_RETRIES}...")
    try:
        # Use urlretrieve with a longer timeout
        opener = urllib.request.build_opener()
        opener.addheaders = [("User-Agent", "Mozilla/5.0")]
        urllib.request.install_opener(opener)
        urllib.request.urlretrieve(URL, ZIP_PATH)
        size_mb = os.path.getsize(ZIP_PATH) / (1024 * 1024)
        print(f"Downloaded: {size_mb:.1f} MB")
        if size_mb < 50:
            print("File too small, likely incomplete. Retrying...")
            os.remove(ZIP_PATH)
            time.sleep(5)
            continue
        break
    except Exception as e:
        print(f"Download error: {e}")
        if os.path.exists(ZIP_PATH):
            os.remove(ZIP_PATH)
        if attempt < MAX_RETRIES:
            time.sleep(10)
        else:
            print("All download attempts failed.")
            sys.exit(1)

# Verify ZIP integrity
print("Verifying ZIP integrity...")
try:
    with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
        bad = zf.testzip()
        if bad:
            print(f"Corrupt file in ZIP: {bad}")
            sys.exit(1)
        names = zf.namelist()
        print(f"ZIP contains {len(names)} files")
        for n in names[:20]:
            print(f"  {n}")
        if len(names) > 20:
            print(f"  ... and {len(names)-20} more")
except zipfile.BadZipFile as e:
    print(f"BAD ZIP: {e}")
    sys.exit(1)

# Extract
print("Extracting...")
with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
    zf.extractall(OLLAMA_DIR)

# Find ollama.exe
for root, dirs, files in os.walk(OLLAMA_DIR):
    for f in files:
        if f.lower() == "ollama.exe":
            full = os.path.join(root, f)
            print(f"SUCCESS: {full}")
            # Quick version check
            import subprocess
            result = subprocess.run([full, "--version"], capture_output=True, text=True, timeout=10)
            print(f"VERSION: {result.stdout.strip() or result.stderr.strip()}")
            sys.exit(0)

print("ERROR: ollama.exe not found after extraction")
sys.exit(1)
