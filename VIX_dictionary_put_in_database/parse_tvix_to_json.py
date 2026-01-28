import json
from pathlib import Path


# 單檔解析器：直接執行本檔會解析預設樣本檔案
src = Path(r"D:\Business_Cycle_stratgy\VIX_dictionary_put_in_database\TFE_rawdata\tvix_20251001")
out = src.with_suffix(".json")

def read_text_with_fallback(p: Path) -> str:
    for enc in ("cp950", "utf-8-sig", "utf-8"):
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    # 最後手段：替換無法解碼字元
    return p.read_text(encoding="utf-8", errors="replace")

text = read_text_with_fallback(src)

lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
if not lines:
    raise ValueError("檔案為空或只有空白")

# 第一行通常是欄名，第二行通常是分隔線 '--------'
data_lines = []
for ln in lines:
    if ln.startswith("--------"):
        continue
    # 跳過欄名列：只要這行含非數字開頭（例如欄名），就跳過
    if not ln[:1].isdigit():
        continue
    data_lines.append(ln)

def _format_date_yyyymmdd(s: str) -> str:
    s2 = "".join(ch for ch in s if ch.isdigit())
    if len(s2) == 8:
        return s2
    return s

def _format_time_raw(s: str) -> str:
    # 檔案中的 time_raw 形如 9000000, 9001500... 推測為 HHMMSScc（cc=百分秒）
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return s
    digits = digits.zfill(8)  # 補到 8 位：HHMMSScc
    hh, mm, ss = digits[0:2], digits[2:4], digits[4:6]
    return f"{hh}:{mm}:{ss}"

rows = []

#批次讀取資料
for i, ln in enumerate(data_lines):
    # 這份檔案看起來是 Tab 分隔；保險起見也支援多空白
    parts_tab = ln.split("\t")
    # 檔案中可能存在連續 tab，會造成 parts_tab 出現空字串，需濾掉
    parts = [p for p in parts_tab if p.strip() != ""]
    if len(parts) < 3:
        parts = ln.split()
    if len(parts) < 3:
        continue

    yyyymmdd = parts[0].strip()
    t_raw = parts[1].strip()
    # 第三欄可能因為多 tab 對齊跑到更後面，取最後一欄最保險
    vix_raw = parts[-1].strip()

    # vix
    try:
        vix = float(vix_raw)
    except ValueError:
        vix = None

    date_fmt = _format_date_yyyymmdd(yyyymmdd)
    time_fmt = _format_time_raw(t_raw)

    rows.append({
        "date": yyyymmdd,          # 格式 A：YYYYMMDD（TEXT，符合資料庫格式）
        "time": time_fmt,          # 格式 A：HH:MM:SS（TEXT，符合資料庫格式）
        "vix": vix                 # 例如：21.76
    })

out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OK: parsed {len(rows)} rows -> {out}")