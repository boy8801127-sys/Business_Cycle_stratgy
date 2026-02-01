"""
VIX_data 衍生指標計算並寫回資料庫
從 VIX_data 月 K 線（open, high, low, close）計算衍生指標，寫入同表欄位。
匯出 Orange 時僅從資料庫讀取，不在匯出時即時計算。
"""

import pandas as pd
import numpy as np
from typing import Optional

from data_collection.database_manager import DatabaseManager


def _normalize_trade_date(s: str) -> str:
    """將 tradeDate 轉為 YYYYMMDD 以便排序（若為 6 碼補 01）。"""
    if not s or pd.isna(s):
        return ""
    s = str(s).strip()
    if len(s) == 6:
        return s + "01"
    return s[:8]


def compute_and_save_vix_derivatives(
    db_manager: Optional[DatabaseManager] = None,
    db_path: str = "D:\\all_data\\taiwan_stock_all_data.db",
) -> bool:
    """
    讀取 VIX_data，計算衍生指標並寫回資料庫。
    衍生欄位：vix_change, vix_change_pct, vix_range, vix_range_pct, vix_mom,
             vix_close_lag1, vix_close_lag2, vix_ma3, vix_ma6
    若 VIX_data 不存在或為空則回傳 False。
    """
    if db_manager is None:
        db_manager = DatabaseManager(db_path=db_path)

    if not db_manager.check_table_exists("VIX_data"):
        print("[Warning] VIX_data 資料表不存在，跳過衍生指標計算")
        return False

    db_manager.ensure_vix_data_derivative_columns()

    df = db_manager.get_vix_data()
    if df.empty or len(df) == 0:
        print("[Warning] VIX_data 為空，跳過衍生指標計算")
        return False

    df = df.copy()
    df["_tradeDate_norm"] = df["tradeDate"].astype(str).apply(_normalize_trade_date)
    df = df.sort_values("_tradeDate_norm").reset_index(drop=True)

    open_ = df["open"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    df["vix_change"] = close - open_
    df["vix_change_pct"] = np.where(open_ != 0, (close - open_) / open_ * 100, np.nan)
    df["vix_range"] = high - low
    df["vix_range_pct"] = np.where(open_ != 0, (high - low) / open_ * 100, np.nan)

    prev_close = close.shift(1)
    df["vix_close_lag1"] = prev_close
    df["vix_close_lag2"] = close.shift(2)
    df["vix_mom"] = np.where(prev_close != 0, (close - prev_close) / prev_close * 100, np.nan)
    df["vix_ma3"] = close.rolling(3, min_periods=1).mean()
    df["vix_ma6"] = close.rolling(6, min_periods=1).mean()

    conn = db_manager.get_connection()
    cursor = conn.cursor()
    updated = 0
    try:
        for _, row in df.iterrows():
            trade_date = str(row["tradeDate"]).strip()
            cursor.execute(
                """
                UPDATE VIX_data SET
                    vix_change = ?, vix_change_pct = ?, vix_range = ?, vix_range_pct = ?,
                    vix_mom = ?, vix_close_lag1 = ?, vix_close_lag2 = ?, vix_ma3 = ?, vix_ma6 = ?
                WHERE tradeDate = ?
                """,
                (
                    row.get("vix_change") if pd.notna(row.get("vix_change")) else None,
                    row.get("vix_change_pct") if pd.notna(row.get("vix_change_pct")) else None,
                    row.get("vix_range") if pd.notna(row.get("vix_range")) else None,
                    row.get("vix_range_pct") if pd.notna(row.get("vix_range_pct")) else None,
                    row.get("vix_mom") if pd.notna(row.get("vix_mom")) else None,
                    row.get("vix_close_lag1") if pd.notna(row.get("vix_close_lag1")) else None,
                    row.get("vix_close_lag2") if pd.notna(row.get("vix_close_lag2")) else None,
                    row.get("vix_ma3") if pd.notna(row.get("vix_ma3")) else None,
                    row.get("vix_ma6") if pd.notna(row.get("vix_ma6")) else None,
                    trade_date,
                ),
            )
            updated += cursor.rowcount
        conn.commit()
        print(f"[Info] VIX_data 衍生指標已更新，共 {updated} 筆")
        return True
    except Exception as e:
        conn.rollback()
        print(f"[Error] 更新 VIX_data 衍生指標失敗: {e}")
        raise
    finally:
        conn.close()
