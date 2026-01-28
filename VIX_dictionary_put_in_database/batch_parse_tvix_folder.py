import json
import re
from pathlib import Path

FOLDER = Path(r"D:\Business_Cycle_stratgy\VIX_dictionary_put_in_database\TFE_rawdata\當月資料")

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

def parse_one_file(src: Path) -> list[dict]:
    text = read_text_with_fallback(src)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    rows: list[dict] = []
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

    return rows

def main():
    if not FOLDER.exists():
        raise FileNotFoundError(f"資料夾不存在: {FOLDER}")

    targets = sorted(FOLDER.glob("*_new.txt"))
    print(f"[Info] folder={FOLDER} files={len(targets)}")

    ok = 0
    for src in targets:
        # 命名規則：tvix_YYYYMMDD.json（輸出仍放在當月資料資料夾）
        m = re.search(r"(\d{8})", src.stem)  # src.stem 例：20260102_new
        if not m:
            raise ValueError(f"檔名找不到 8 碼日期: {src.name}")
        yyyymmdd = m.group(1)
        out = src.with_name(f"tvix_{yyyymmdd}.json")
        rows = parse_one_file(src)
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"OK: {src.name} -> {out.name} rows={len(rows)}")
        ok += 1

    print(f"[Info] done ok={ok}")

if __name__ == "__main__":
    main()