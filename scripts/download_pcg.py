"""Download the CinC-2016 training-a heart-sound set from PhysioNet (once)."""
import sys
from pathlib import Path
import httpx

BASE = "https://physionet.org/files/challenge-2016/1.0.0/training-a"
OUT = Path(__file__).resolve().parents[1] / "data" / "pcg" / "training-a"
OUT.mkdir(parents=True, exist_ok=True)

c = httpx.Client(timeout=60, follow_redirects=True)
ref = c.get(f"{BASE}/REFERENCE.csv").text
(OUT / "REFERENCE.csv").write_text(ref, encoding="utf-8")
records = [ln.split(",")[0] for ln in ref.splitlines() if ln.strip()]
print(f"{len(records)} records")

done = 0
for rec in records:
    dest = OUT / f"{rec}.wav"
    if dest.exists() and dest.stat().st_size > 0:
        done += 1
        continue
    try:
        r = c.get(f"{BASE}/{rec}.wav")
        r.raise_for_status()
        dest.write_bytes(r.content)
        done += 1
        if done % 50 == 0:
            print(f"  {done}/{len(records)}")
    except Exception as e:
        print(f"  FAILED {rec}: {e}", file=sys.stderr)

total = sum(p.stat().st_size for p in OUT.glob("*.wav"))
print(f"done: {done}/{len(records)} wavs, {total/1024/1024:.1f} MB")
