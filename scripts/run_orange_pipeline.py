"""
Orange 一鍵 Pipeline：蒐集 → 衍生計算 → 匯出
依序執行 Phase 1 蒐集、Phase 2 衍生計算、Phase 3 匯出 Orange CSV。
"""

import os
import sys
import argparse
import time
from pathlib import Path
from datetime import datetime
from calendar import monthrange

# 專案根目錄
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 切換到專案根目錄，使 business_cycle 等路徑正確
os.chdir(PROJECT_ROOT)

import pandas as pd
import pandas_market_calendars as pmc

from data_collection.database_manager import DatabaseManager
from data_collection.cycle_data_collector import CycleDataCollector
from data_collection.indicator_data_collector import IndicatorDataCollector
from data_collection.stock_data_collector import StockDataCollector
from data_collection.otc_data_collector import OTCDataCollector
from data_collection.margin_data_collector import MarginDataCollector
from data_collection.technical_indicator_calculator import TechnicalIndicatorCalculator


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Orange 一鍵 Pipeline：蒐集 → 衍生計算 → 匯出"
    )
    parser.add_argument(
        "--skip-collect",
        action="store_true",
        help="略過 Phase 1 蒐集",
    )
    parser.add_argument(
        "--skip-derive",
        action="store_true",
        help="略過 Phase 2 衍生計算",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="略過 Phase 3 匯出 Orange CSV",
    )
    parser.add_argument(
        "--no-otc",
        action="store_true",
        help="不蒐集上櫃股票",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2015-01-01",
        help="起始日期 YYYY-MM-DD（預設 2015-01-01）",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="結束日期 YYYY-MM-DD（預設今天）",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default="006208,2330",
        help="股票代號逗號分隔（預設 006208,2330）",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=r"D:\all_data\taiwan_stock_all_data.db",
        help="SQLite 資料庫路徑",
    )
    return parser.parse_args()


def _to_yyyymmdd(s: str) -> str:
    if not s or s.strip() == "":
        return s
    return s.strip().replace("-", "")


def phase1_collect(args, db_manager: DatabaseManager):
    """Phase 1：蒐集資料（景氣、股價、融資融券、VIX）"""
    print("\n" + "=" * 60)
    print("Phase 1：蒐集資料")
    print("=" * 60)

    # 1. 景氣燈號與指標（從 CSV）
    print("\n[1/4] 景氣燈號與指標（CSV 匯入）...")
    db_manager.init_all_indicator_tables()
    csv_path = PROJECT_ROOT / "business_cycle" / "景氣指標與燈號.csv"
    if csv_path.exists():
        cycle_collector = CycleDataCollector(str(csv_path))
        daily_df = cycle_collector.process_cycle_data()
        if not daily_df.empty:
            cycle_collector.save_cycle_data_to_db(db_manager)
            print(f"  [OK] 景氣燈號 {len(daily_df)} 筆")
        else:
            print("  [Warning] 景氣燈號 CSV 無資料")
    else:
        print(f"  [Warning] 找不到 {csv_path}，跳過景氣燈號")
    indicator_collector = IndicatorDataCollector(base_path=str(PROJECT_ROOT / "business_cycle"))
    results = indicator_collector.import_all_indicators(db_manager)
    success = sum(1 for r in results.values() if r.get("success"))
    print(f"  [OK] 景氣指標 {success}/{len(results)} 個表匯入完成")

    # 2. 上市股票與 ETF（可選上櫃）
    print("\n[2/4] 上市股票與 ETF...")
    start_yyyymmdd = _to_yyyymmdd(args.start_date)
    days = 9999
    stock_collector = StockDataCollector(db_manager)
    result = stock_collector.batch_fetch_stock_prices_only(days=days, start_date=start_yyyymmdd)
    print(f"  [OK] 成功 {result['success']} 天，失敗 {result['failed']}，跳過 {result['skipped']}")
    if not args.no_otc:
        print("  上櫃股票...")
        otc_collector = OTCDataCollector(db_manager)
        otc_result = otc_collector.batch_fetch_otc_data(days=days, start_date=start_yyyymmdd)
        print(f"  [OK] 上櫃 成功 {otc_result['success']} 天")

    # 3. 融資融券（僅原始欄位，衍生在 Phase 2）
    print("\n[3/4] 融資融券...")
    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    margin_collector = MarginDataCollector(db_manager, polite_sleep=5)
    margin_result = margin_collector.batch_fetch_margin_data(
        start_date=args.start_date,
        end_date=end_date,
        retry_times=3,
        retry_delay=5,
    )
    print(f"  [OK] 成功 {margin_result['success']} 筆，失敗 {margin_result['failed']}，跳過 {margin_result['skipped']}")

    # 4. VIX 原始與月 K（當月）
    print("\n[4/4] VIX 下載與月 K 線...")
    try:
        from main import (
            download_vix_data,
            parse_and_save_to_tfe_vix,
            recalculate_monthly_kline,
            update_vix_data_monthly_kline,
        )
    except ImportError:
        print("  [Warning] 無法從 main 匯入 VIX 函數，跳過 VIX")
        return
    now = datetime.now()
    year_month = now.strftime("%Y%m")
    year, month = now.year, now.month
    first_day = datetime(year, month, 1)
    last_day_num = monthrange(year, month)[1]
    last_day = datetime(year, month, last_day_num)
    cal = pmc.get_calendar("XTAI")
    trading_days = cal.valid_days(start_date=pd.Timestamp(first_day), end_date=pd.Timestamp(last_day))
    trading_days_str = [day.strftime("%Y%m%d") for day in trading_days]
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT date FROM TFE_VIX_data WHERE date LIKE ?", (f"{year_month}%",))
    existing_dates = set(row[0] for row in cursor.fetchall())
    conn.close()
    missing_dates = [d for d in trading_days_str if d not in existing_dates]
    downloaded_files = []
    if missing_dates:
        raw_data_folder = PROJECT_ROOT / "VIX_dictionary_put_in_database" / "TFE_rawdata" / "raw_data"
        raw_data_folder.mkdir(parents=True, exist_ok=True)
        for date_str in missing_dates:
            save_path = raw_data_folder / f"{date_str}_new.txt"
            downloaded_file = download_vix_data(date_str, save_path, retry_times=3, retry_delay=5)
            if downloaded_file:
                downloaded_files.append(downloaded_file)
            time.sleep(2)
        for f in downloaded_files:
            parse_and_save_to_tfe_vix(f, db_manager)
    kline_data = recalculate_monthly_kline(year_month, db_manager)
    if kline_data:
        update_vix_data_monthly_kline(year_month, kline_data, db_manager)
        print(f"  [OK] VIX 當月 {year_month} 月 K 線已更新")
    else:
        print("  [Warning] 當月無 VIX K 線資料")


def phase2_derive(args, db_manager: DatabaseManager):
    """Phase 2：計算衍生數據"""
    print("\n" + "=" * 60)
    print("Phase 2：計算衍生數據")
    print("=" * 60)

    # 1. M1B 年增率等
    print("\n[1/6] M1B 年增率...")
    try:
        from data_collection.m1b_calculator import M1BCalculator
        calculator = M1BCalculator()
        update_stats = calculator.calculate_and_update(db_manager)
        if update_stats.get("success"):
            print("  [OK] M1B 年增率計算完成")
        else:
            print("  [Warning] M1B 無更新或失敗")
    except Exception as e:
        print(f"  [Warning] M1B 跳過: {e}")

    # 1.5 綜合指標衍伸
    print("\n[1.5/6] 綜合指標衍伸...")
    try:
        indicator_collector = IndicatorDataCollector(base_path=str(PROJECT_ROOT / "business_cycle"))
        indicator_collector.calculate_and_save_composite_derived_indicators(db_manager)
        print("  [OK] composite_indicators_data 衍伸已更新")
    except Exception as e:
        print(f"  [Warning] 綜合指標衍伸跳過: {e}")

    # 2. 合併總經指標
    print("\n[2/6] 合併總經指標...")
    indicator_collector = IndicatorDataCollector(base_path=str(PROJECT_ROOT / "business_cycle"))
    try:
        indicator_collector.calculate_and_save_merged_indicators(db_manager)
        print("  [OK] merged_economic_indicators 已更新")
    except Exception as e:
        print(f"  [Warning] 合併總經跳過: {e}")

    # 3. 融資融券衍生
    print("\n[3/6] 融資融券衍生指標...")
    margin_collector = MarginDataCollector(db_manager)
    margin_collector.calculate_derived_indicators()
    print("  [OK] 衍生指標計算完成")

    # 4. VIX 衍生
    print("\n[4/6] VIX 衍生指標...")
    try:
        from data_collection.vix_derivatives import compute_and_save_vix_derivatives
        compute_and_save_vix_derivatives(db_manager=db_manager)
        print("  [OK] VIX_data 衍生欄位已更新")
    except Exception as e:
        print(f"  [Warning] VIX 衍生跳過: {e}")

    # 5. 技術指標日線 / 月線
    print("\n[5/6] 技術指標日線...")
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    start_yyyymmdd = _to_yyyymmdd(args.start_date)
    end_yyyymmdd = _to_yyyymmdd(args.end_date or datetime.now().strftime("%Y-%m-%d"))
    tech_calc = TechnicalIndicatorCalculator(db_path=args.db_path)
    tech_calc.calculate_and_save_daily(tickers=tickers, start_date=start_yyyymmdd, end_date=end_yyyymmdd, if_exists="replace")
    print("  [OK] stock_technical_indicators 已更新")
    print("\n[6/6] 技術指標月線...")
    tech_calc.calculate_and_save_monthly(tickers=tickers, start_date=start_yyyymmdd, end_date=end_yyyymmdd, if_exists="replace")
    print("  [OK] stock_technical_indicators_monthly 已更新")


def phase3_export(args):
    """Phase 3：匯出 Orange 日線與月線 CSV"""
    print("\n" + "=" * 60)
    print("Phase 3：匯出 Orange CSV")
    print("=" * 60)
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "export_orange_data",
        PROJECT_ROOT / "scripts" / "export_orange_data.py",
    )
    export_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export_module)
    export_orange_data_daily = export_module.export_orange_data_daily
    export_orange_data_monthly = export_module.export_orange_data_monthly
    start_date = args.start_date
    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    print("\n  日線 CSV...")
    export_orange_data_daily(
        start_date=start_date,
        end_date=end_date,
        tickers=tickers,
        db_path=args.db_path,
    )
    print("\n  月線 CSV...")
    export_orange_data_monthly(
        start_date=start_date,
        end_date=end_date,
        tickers=tickers,
        db_path=args.db_path,
    )
    print("\n  [OK] Phase 3 完成")


def run_with_options(
    skip_collect=False,
    skip_derive=False,
    skip_export=False,
    no_otc=False,
    start_date="2015-01-01",
    end_date=None,
    tickers="006208,2330",
    db_path=None,
):
    """
    供 main.py 選項 18 呼叫：以指定選項執行 Orange Pipeline。
    """
    if db_path is None:
        db_path = r"D:\all_data\taiwan_stock_all_data.db"
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    class Args:
        pass

    args = Args()
    args.skip_collect = skip_collect
    args.skip_derive = skip_derive
    args.skip_export = skip_export
    args.no_otc = no_otc
    args.start_date = start_date
    args.end_date = end_date
    args.tickers = tickers
    args.db_path = db_path

    print("\n[Orange Pipeline] 開始執行")
    print(f"  略過蒐集: {args.skip_collect}, 略過衍生: {args.skip_derive}, 略過匯出: {args.skip_export}")
    print(f"  上櫃: {not args.no_otc}, 區間: {args.start_date} ~ {args.end_date or '今天'}, tickers: {args.tickers}")
    db_manager = DatabaseManager(db_path=args.db_path)

    if not args.skip_collect:
        phase1_collect(args, db_manager)
    else:
        print("\n[Phase 1] 已略過")

    if not args.skip_derive:
        phase2_derive(args, db_manager)
    else:
        print("\n[Phase 2] 已略過")

    if not args.skip_export:
        phase3_export(args)
    else:
        print("\n[Phase 3] 已略過")

    print("\n[Orange Pipeline] 全部完成")


def main():
    args = _parse_args()
    print("\n[Orange Pipeline] 開始執行")
    print(f"  略過蒐集: {args.skip_collect}, 略過衍生: {args.skip_derive}, 略過匯出: {args.skip_export}")
    print(f"  上櫃: {not args.no_otc}, 區間: {args.start_date} ~ {args.end_date or '今天'}, tickers: {args.tickers}")
    db_manager = DatabaseManager(db_path=args.db_path)

    if not args.skip_collect:
        phase1_collect(args, db_manager)
    else:
        print("\n[Phase 1] 已略過")

    if not args.skip_derive:
        phase2_derive(args, db_manager)
    else:
        print("\n[Phase 2] 已略過")

    if not args.skip_export:
        phase3_export(args)
    else:
        print("\n[Phase 3] 已略過")

    print("\n[Orange Pipeline] 全部完成")


if __name__ == "__main__":
    main()
