import sqlite3
import math

import numpy as np
import pandas as pd

import os
import sys

# 確保可匯入專案模組
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.export_orange_data import get_column_chinese_mapping


def _pick_rows(df: pd.DataFrame) -> pd.DataFrame:
    picks = []
    for t in sorted(df["股票代號"].unique().tolist()):
        g = df[df["股票代號"] == t].sort_values("日期")
        idxs = [0, min(19, len(g) - 1), len(g) - 1]
        picks.append(g.iloc[idxs])
    return pd.concat(picks, ignore_index=True)


def main():
    csv_path = r"D:\Business_Cycle_stratgy\results\orange_monthly_ohlcv_with_indicators_006208_2330.csv"
    db_path = r"D:\all_data\taiwan_stock_all_data.db"

    csv = pd.read_csv(csv_path)
    csv["日期"] = pd.to_datetime(csv["日期"])

    mapping = get_column_chinese_mapping()
    col_margin = mapping.get("short_margin_ratio", "券資比")
    db_col_m1b = "leading_m1b_money_supply"
    col_m1b = mapping.get(db_col_m1b, "領先_貨幣總計數M1B(百萬元)")

    need_cols = ["日期", "股票代號", col_margin, col_m1b]
    need_cols = [c for c in need_cols if c in csv.columns]
    df = csv[need_cols].copy()

    pick = _pick_rows(df)

    conn = sqlite3.connect(db_path)
    margin = pd.read_sql_query("SELECT date, short_margin_ratio FROM market_margin_data", conn)
    margin["date"] = pd.to_datetime(margin["date"].astype(str), format="%Y%m%d", errors="coerce")
    margin = margin.dropna().sort_values("date")

    cols = pd.read_sql_query("PRAGMA table_info(merged_economic_indicators)", conn)
    colset = set(cols["name"].tolist())
    if db_col_m1b not in colset:
        raise SystemExit(f"merged_economic_indicators 缺 {db_col_m1b} 欄位")

    ind = pd.read_sql_query(f"SELECT indicator_date, {db_col_m1b} FROM merged_economic_indicators", conn)
    ind["indicator_date"] = pd.to_datetime(ind["indicator_date"].astype(str), format="%Y%m%d", errors="coerce")
    ind = ind.dropna(subset=["indicator_date"]).sort_values("indicator_date")

    rows = []
    for _, r in pick.iterrows():
        month_end = r["日期"]

        msub = margin[margin["date"] <= month_end]
        m_val = float(msub.iloc[-1]["short_margin_ratio"]) if len(msub) else np.nan

        target_month = month_end.replace(day=1)
        indicator_month = target_month - pd.DateOffset(months=2)
        mm = ind[
            (ind["indicator_date"].dt.year == indicator_month.year)
            & (ind["indicator_date"].dt.month == indicator_month.month)
        ]
        ind_val = float(mm.iloc[0][db_col_m1b]) if len(mm) else np.nan

        csv_m = float(r[col_margin]) if col_margin in r and pd.notna(r[col_margin]) else np.nan
        csv_m1b = float(r[col_m1b]) if col_m1b in r and pd.notna(r[col_m1b]) else np.nan

        rows.append(
            {
                "ticker": r["股票代號"],
                "date": month_end.strftime("%Y-%m-%d"),
                "csv_short_margin_ratio": csv_m,
                "db_short_margin_ratio": m_val,
                "diff_short_margin_ratio": (csv_m - m_val)
                if (not np.isnan(csv_m) and not np.isnan(m_val))
                else np.nan,
                "csv_leading_m1b": csv_m1b,
                "db_leading_m1b": ind_val,
                "diff_leading_m1b": (csv_m1b - ind_val)
                if (not np.isnan(csv_m1b) and not np.isnan(ind_val))
                else np.nan,
            }
        )

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))

    ok_margin = True
    for d in out["diff_short_margin_ratio"].tolist():
        if d is None or (isinstance(d, float) and math.isnan(d)):
            continue
        if abs(d) >= 1e-9:
            ok_margin = False
            break

    ok_m1b = True
    for d in out["diff_leading_m1b"].tolist():
        if d is None or (isinstance(d, float) and math.isnan(d)):
            continue
        if abs(d) >= 1e-6:
            ok_m1b = False
            break

    print("\nOK margin:", ok_margin)
    print("OK leading_m1b:", ok_m1b)
    conn.close()


if __name__ == "__main__":
    main()

