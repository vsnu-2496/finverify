import os
import sys
import requests
from pathlib import Path

url = "https://huggingface.co/microsoft/deberta-v3-base/resolve/main/pytorch_model.bin"
target_dir = Path(os.path.expanduser(r"~\.cache\huggingface\hub\models--microsoft--deberta-v3-base\snapshots\8ccc9b6f36199bec6961081d44eb72fb3f7353f3"))
target_dir.mkdir(parents=True, exist_ok=True)
target_file = target_dir / "pytorch_model.bin"

print(f"Downloading from {url} to {target_file}...")
response = requests.get(url, stream=True, timeout=30)
response.raise_for_status()

total_size = int(response.headers.get("content-length", 0))
print(f"Total size: {total_size / (1024*1024):.2f} MB")

downloaded = 0
chunk_size = 1024 * 1024  # 1MB
with open(target_file, "wb") as f:
    for chunk in response.iter_content(chunk_size=chunk_size):
        if chunk:
            f.write(chunk)
            downloaded += len(chunk)
            if downloaded % (50 * 1024 * 1024) < chunk_size:
                print(f"Downloaded {downloaded / (1024*1024):.1f} / {total_size / (1024*1024):.1f} MB ({downloaded/total_size*100:.1f}%)")

print("Download complete!")
print("Final file size:", target_file.stat().st_size)
