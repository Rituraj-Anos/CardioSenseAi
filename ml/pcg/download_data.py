"""Download PhysioNet/CinC-2016 heart-sound data for PCG training.

Pulls .wav recordings + normal/abnormal labels from selected training sets into
data/pcg/. One-time; skips files already present.

Dataset: PhysioNet/CinC Challenge 2016 Heart Sound Database.
Verify current access terms at physionet.org/content/challenge-2016/ before use.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "data" / "pcg"
BASE = "https://physionet.org/files/challenge-2016/1.0.0"

# training-a (409) and training-b (490) give ~900 recordings — enough to train a
# real classifier while keeping the download modest. Add more sets for more data.
SETS = ["training-a", "training-b"]
MAX_PER_SET = 260  # cap per set to keep the download bounded for a demo build


def download() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=60, follow_redirects=True)
    total = 0

    for s in SETS:
        set_dir = OUT / s
        set_dir.mkdir(exist_ok=True)
        ref = client.get(f"{BASE}/{s}/REFERENCE.csv")
        ref.raise_for_status()
        (set_dir / "REFERENCE.csv").write_text(ref.text, encoding="utf-8")

        records = [line.split(",")[0] for line in ref.text.strip().splitlines() if line]
        records = records[:MAX_PER_SET]
        print(f"{s}: {len(records)} recordings")

        for i, rec in enumerate(records):
            dest = set_dir / f"{rec}.wav"
            if dest.exists() and dest.stat().st_size > 0:
                continue
            try:
                r = client.get(f"{BASE}/{s}/{rec}.wav")
                if r.status_code == 200 and r.content:
                    dest.write_bytes(r.content)
                    total += 1
            except Exception as e:
                print(f"  skip {rec}: {e}")
            if (i + 1) % 50 == 0:
                print(f"  {s}: {i + 1}/{len(records)}")

    print(f"Downloaded {total} new .wav files into {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    download()
