"""Download CNN14 PANNs checkpoint weights to models/."""

import os
import sys
import urllib.request

CHECKPOINT_URL = (
    "https://zenodo.org/record/3987831/files/Cnn14_mAP%3D0.431.pth"
)
DEST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "models", "Cnn14_mAP=0.431.pth"
)


def _progress(block_num: int, block_size: int, total_size: int) -> None:
    """Simple progress bar for urllib.request.urlretrieve."""
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(downloaded / total_size * 100, 100)
        filled = int(pct / 2)
        bar = "#" * filled + "-" * (50 - filled)
        sys.stdout.write(f"\r  [{bar}] {pct:5.1f}%  ({downloaded // 1_048_576} MB)")
        sys.stdout.flush()
        if downloaded >= total_size:
            print()


def main() -> None:
    """Download Cnn14_mAP=0.431.pth if not already present."""
    dest = os.path.normpath(DEST_PATH)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if os.path.exists(dest):
        size_mb = os.path.getsize(dest) / 1_048_576
        print(f"[SoundSense] Weights already present at {dest} ({size_mb:.1f} MB) — skipping.")
        return

    print(f"[SoundSense] Downloading CNN14 weights to {dest} ...")
    urllib.request.urlretrieve(CHECKPOINT_URL, dest, reporthook=_progress)
    size_mb = os.path.getsize(dest) / 1_048_576
    print(f"[SoundSense] Download complete: {dest} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
