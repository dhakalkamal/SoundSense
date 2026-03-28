"""Download AudioSet class label CSV to models/."""

import os
import urllib.request

LABELS_URL = (
    "https://raw.githubusercontent.com/qiuqiangkong/audioset_tagging_cnn"
    "/master/metadata/class_labels_indices.csv"
)
DEST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "models", "class_labels_indices.csv"
)


def main() -> None:
    """Download class_labels_indices.csv if not already present."""
    dest = os.path.normpath(DEST_PATH)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if os.path.exists(dest):
        print(f"[SoundSense] AudioSet labels already present at {dest} — skipping.")
        return

    print(f"[SoundSense] Downloading AudioSet labels to {dest} ...")
    urllib.request.urlretrieve(LABELS_URL, dest)
    print(f"[SoundSense] Download complete: {dest}")


if __name__ == "__main__":
    main()
