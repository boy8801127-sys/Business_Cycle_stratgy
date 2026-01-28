import json
from pathlib import Path

SRC = Path(r"D:\Business_Cycle_stratgy\VIX_dictionary_put_in_database\TFE_rawdata\當月資料\20260102_new.txt")
OUT = SRC.with_suffix(".json")

def read_text_with_fallback(p: Path) -> str:
    for enc in ("cp950", "utf-8-sig", "utf-8"):
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return p.read_text(encoding="utf-8", errors="replace")

def time_raw_to_hms(s: str) -> str:
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return s
    digits = digits.zfill(8)  # HHMMSScc
    hh, mm, ss = digits[0:2], digits[2:4], digits[4:6]
    return f"{hh}:{mm}:{ss}"

text = read_text_with_fallback(SRC)
lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

rows = []
for ln in lines:
    if ln.startswith("--------"):
        continue
    if not ln[:1].isdigit():  # 跳過表頭、Last 1 min AVG 等
        continue

    parts_tab = ln.split("\t")
    parts = [p for p in parts_tab if p.strip() != ""]
    if len(parts) < 3:
        parts = ln.split()
    if len(parts) < 3:
        continue

    date = parts[0].strip()         # YYYYMMDD
    time_raw = parts[1].strip()     # 9000000
    vix_raw = parts[-1].strip()     # 最後欄

    try:
        vix = float(vix_raw)
    except ValueError:
        vix = None

    rows.append({"date": date, "time": time_raw_to_hms(time_raw), "vix": vix})

OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OK: {SRC.name} -> {OUT.name} rows={len(rows)}")