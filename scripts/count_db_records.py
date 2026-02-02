"""
統計 taiwan_stock_all_data.db 各表筆數與細分類，供簡報使用。
執行：python scripts/count_db_records.py
輸出：終端機印出 + results/資料庫筆數統計.txt
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("DB_PATH", r"D:\all_data\taiwan_stock_all_data.db")

TABLE_LABELS = {
    "tw_stock_price_data": "上市/ETF 股價",
    "tw_otc_stock_price_data": "上櫃股價",
    "tw_price_indices_data": "價格指數",
    "tw_return_indices_data": "報酬指數",
    "business_cycle_data": "景氣燈號",
    "leading_indicators_data": "領先指標",
    "coincident_indicators_data": "同時指標",
    "lagging_indicators_data": "落後指標",
    "composite_indicators_data": "綜合指標與燈號",
    "business_cycle_signal_components_data": "景氣信號構成",
    "market_margin_data": "融資融券",
    "merged_economic_indicators": "合併總經指標",
    "stock_technical_indicators": "技術指標(日線)",
    "stock_technical_indicators_monthly": "技術指標(月線)",
    "etf_006208_monthly_future": "006208 月線未來",
    "TFE_VIX_data": "VIX 原始(TFE)",
    "VIX_data": "VIX 月K/衍生",
    "twse_margin_data": "融資融券(證交所)",
    "strategy_result": "策略回測結果",
}


def main():
    if not os.path.exists(DB_PATH):
        print(f"找不到資料庫: {DB_PATH}")
        return
    conn = __import__("sqlite3").connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]

    total_rows = 0
    lines = []
    lines.append("=" * 60)
    lines.append("資料庫筆數統計（可貼入簡報）")
    lines.append("=" * 60)

    for name in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM [{name}]")
            n = cur.fetchone()[0]
        except Exception as e:
            n = -1
            lines.append(f"  {name}: 查詢失敗 ({e})")
            continue
        total_rows += n
        label = TABLE_LABELS.get(name, name)
        lines.append(f"  {label}: {n:,} 筆")

    lines.append("-" * 60)
    lines.append(f"  總筆數（所有表合計）: {total_rows:,} 筆")
    lines.append("")

    # 細分類：上市股價
    if "tw_stock_price_data" in tables:
        try:
            cur.execute("SELECT COUNT(DISTINCT ticker) FROM tw_stock_price_data")
            n_ticker = cur.fetchone()[0]
            cur.execute("SELECT MIN(date), MAX(date) FROM tw_stock_price_data")
            min_d, max_d = cur.fetchone()
            lines.append("【細分類】上市/ETF 股價")
            lines.append(f"  標的數: {n_ticker}，日期區間: {min_d} ~ {max_d}")
            lines.append("")
        except Exception:
            pass

    # 細分類：上櫃股價
    if "tw_otc_stock_price_data" in tables:
        try:
            cur.execute("SELECT COUNT(DISTINCT ticker) FROM tw_otc_stock_price_data")
            n_ticker = cur.fetchone()[0]
            cur.execute("SELECT MIN(date), MAX(date) FROM tw_otc_stock_price_data")
            min_d, max_d = cur.fetchone()
            lines.append("【細分類】上櫃股價")
            lines.append(f"  標的數: {n_ticker}，日期區間: {min_d} ~ {max_d}")
            lines.append("")
        except Exception:
            pass

    # 細分類：景氣/綜合指標
    for t, label in [
        ("composite_indicators_data", "綜合指標"),
        ("business_cycle_data", "景氣燈號"),
    ]:
        if t in tables:
            try:
                cur.execute(f"SELECT COUNT(*), MIN(date), MAX(date) FROM [{t}]")
                n, min_d, max_d = cur.fetchone()
                lines.append(f"【細分類】{label}")
                lines.append(f"  筆數: {n:,}，區間: {min_d} ~ {max_d}")
                lines.append("")
            except Exception:
                pass

    conn.close()
    text = "\n".join(lines)
    print(text)

    out_dir = PROJECT_ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "資料庫筆數統計.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\n已寫入: {out_file}")


if __name__ == "__main__":
    main()
