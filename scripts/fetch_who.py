"""One-time offline pull of WHO GHO indicators for India. Writes static JSON."""
import json
from datetime import date
from pathlib import Path
import httpx

BASE = "https://ghoapi.azureedge.net/api/"
OUT = Path(__file__).resolve().parents[1] / "frontend" / "src" / "data" / "who_stats.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def pull(code: str):
    r = httpx.get(f"{BASE}{code}?$filter=SpatialDim eq 'IND'", timeout=40)
    r.raise_for_status()
    return r.json().get("value", [])


def latest_both_sex(rows):
    bt = [d for d in rows if d.get("Dim1") in ("BTSX", None)]
    bt = sorted(bt, key=lambda x: x.get("TimeDim") or 0)
    return bt[-1] if bt else None


result = {"pulled": str(date.today()), "source": "WHO Global Health Observatory OData API", "indicators": {}}
for code in ("NCDMORT3070",):
    try:
        rows = pull(code)
        latest = latest_both_sex(rows)
        if latest:
            result["indicators"][code] = {
                "year": latest.get("TimeDim"),
                "value": latest.get("NumericValue"),
                "low": latest.get("Low"),
                "high": latest.get("High"),
            }
            print(code, latest.get("TimeDim"), latest.get("NumericValue"))
    except Exception as e:
        print("FAILED", code, e)

OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print("wrote", OUT)
