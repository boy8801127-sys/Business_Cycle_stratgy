"""
景氣週期投資策略主執行檔
提供互動式選單和主要功能入口
"""

import os
import sys
from datetime import datetime
import pandas as pd

# 設定編碼（Windows）
if os.name == 'nt':
    try:
        os.system('chcp 65001 > NUL')
    except:
        pass
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding='utf-8')
            except ValueError:
                pass

from data_collection.database_manager import DatabaseManager
from data_collection.cycle_data_collector import CycleDataCollector
from data_collection.stock_data_collector import StockDataCollector
from data_collection.otc_data_collector import OTCDataCollector
from backtesting.backtest_engine import BacktestEngine
from backtesting.strategy import (
    ShortTermBondStrategy, CashStrategy, LongTermBondStrategy,
    InverseETFStrategy, FiftyFiftyStrategy,
    ProportionalAllocationStrategy, TSMCProportionalAllocationStrategy
)
from data_validation.price_validator import PriceValidator


def print_menu():
    """顯示主選單"""
    print("\n" + "="*60)
    print("景氣週期投資策略系統")
    print("="*60)
    print("1. 讀取景氣燈號資料（從 CSV，驗證資料）")
    print("2. 蒐集股票和ETF資料（含禮貌休息）")
    print("3. 執行回測（2015 年至今）")
    print("4. 產生績效報告和圖表")
    print("5. 批次更新資料（含禮貌休息）")
    print("6. 驗證股價資料（檢查異常）")
    print("7. 檢查資料完整性（檢查交易日是否有指定股票資料）")
    print("8. 填補零值價格資料（處理沒有交易的日子）")
    print("9. 刪除上櫃資料表中的權證資料（7開頭六位數）")
    print("0. 離開")
    print("="*60)


def load_cycle_data():
    """選項 1：讀取景氣燈號資料"""
    print("\n[選項 1] 讀取景氣燈號資料")
    print("-" * 60)
    
    csv_path = 'business_cycle/景氣指標與燈號.csv'
    
    collector = CycleDataCollector(csv_path)
    
    try:
        # 處理資料
        start_date = '2015-01-01'
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"處理日期範圍：{start_date} 至 {end_date}")
        daily_df = collector.process_cycle_data(start_date, end_date)
        
        if daily_df.empty:
            print("[Error] 無法讀取景氣燈號資料")
            return
        
        print(f"\n[Info] 成功處理 {len(daily_df)} 筆交易日資料")
        print("\n前 5 筆資料：")
        print(daily_df[['date_str', 'score', 'val_shifted', 'signal']].head())
        
        # 儲存到資料庫（可選）
        save_to_db = input("\n是否儲存到資料庫？(y/n): ").strip().lower()
        if save_to_db == 'y':
            db_manager = DatabaseManager()
            collector.save_cycle_data_to_db(db_manager)
            print("[Info] 資料已儲存到資料庫")
        
    except Exception as e:
        print(f"[Error] 讀取景氣燈號資料失敗: {e}")
        import traceback
        traceback.print_exc()


def collect_stock_data():
    """選項 2：蒐集股票和ETF資料"""
    print("\n[選項 2] 蒐集股票和ETF資料")
    print("-" * 60)
    
    # 詢問是否清除現有資料（從 2015 年重新蒐集）
    clear_data = input("是否清除現有資料並從 2015-01-01 重新蒐集？(y/n，預設 n): ").strip().lower()
    
    db_manager = DatabaseManager()
    
    fetch_otc = input("是否同時蒐集上櫃股票資料？(y/n，預設 y): ").strip().lower()
    if fetch_otc not in ('y', 'n'):
        fetch_otc = 'y'
    
    if clear_data == 'y':
        print("\n[Warning] 即將清除 tw_stock_price_data 表的所有資料...")
        confirm = input("請確認（輸入 'YES' 以確認）: ").strip()
        if confirm == 'YES':
            # 先修改表結構（加入 stock_name 欄位）
            print("\n[步驟 1] 修改表結構（加入 stock_name 欄位）...")
            db_manager.modify_stock_price_table_add_stock_name()
            
            # 清除資料
            print("\n[步驟 2] 清除 tw_stock_price_data 表資料...")
            db_manager.clear_table_data('tw_stock_price_data')
            
            # 清除價格指數和報酬指數資料（可選）
            clear_indices = input("是否同時清除價格指數和報酬指數資料？(y/n，預設 n): ").strip().lower()
            if clear_indices == 'y':
                db_manager.clear_table_data('tw_price_indices_data')
                db_manager.clear_table_data('tw_return_indices_data')
                print("[Info] 已清除所有指數資料")
            
            if fetch_otc == 'y':
                clear_otc = input("是否清除上櫃股票資料？(y/n，預設 y): ").strip().lower()
                if clear_otc not in ('y', 'n'):
                    clear_otc = 'y'
                if clear_otc == 'y':
                    db_manager.clear_table_data('tw_otc_stock_price_data')
                    print("[Info] 已清除上櫃股票資料表資料")
            
            print("[Info] 資料清除完成，將從 2015-01-01 開始重新蒐集")
        else:
            print("[Info] 已取消清除資料操作")
            return
    
    # 詢問起始日期
    start_date_input = input("請輸入起始日期（YYYY-MM-DD，預設 2015-01-01）: ").strip()
    start_date = start_date_input if start_date_input else '2015-01-01'
    
    # 將日期轉換為 YYYYMMDD 格式
    start_date_compact = start_date.replace('-', '')
    days = 9999  # 以大數確保從起始日期回補至今
    
    collector = StockDataCollector(db_manager)
    otc_collector = OTCDataCollector(db_manager) if fetch_otc == 'y' else None
    
    try:
        result = collector.batch_fetch_stock_prices_only(days=days, start_date=start_date_compact)
        print(f"\n[Info] 資料蒐集完成")
        print(f"成功：{result['success']} 天")
        print(f"失敗：{result['failed']} 天")
        print(f"跳過：{result['skipped']} 天")
        
        if fetch_otc == 'y' and otc_collector:
            otc_result = otc_collector.batch_fetch_otc_data(days=days, start_date=start_date_compact)
            print(f"\n[Info] 上櫃資料蒐集完成")
            print(f"成功：{otc_result['success']} 天")
            print(f"失敗：{otc_result['failed']} 天")
            print(f"跳過：{otc_result['skipped']} 天")
        
    except Exception as e:
        print(f"[Error] 資料蒐集失敗: {e}")
        import traceback
        traceback.print_exc()


def run_backtest():
    """選項 3：執行回測"""
    print("\n[選項 3] 執行回測")
    print("-" * 60)
    
    # 選擇策略
    print("\n請選擇策略：")
    print("1. 短天期美債避險（主資產 006208）")
    print("2. 現金避險（主資產 006208）")
    print("3. 長天期美債避險（主資產 006208）")
    print("4. 反向ETF避險（主資產 006208）")
    print("5. 50:50配置（006208 + 短債）")
    print("6. 等比例配置（006208:短期美債）")
    print("7. 等比例配置（台積電:短期美債）")
    
    strategy_choice = input("請選擇（1-7，預設 1）: ").strip()
    strategy_map = {
        '1': ('ShortTermBond', ShortTermBondStrategy),
        '2': ('Cash', CashStrategy),
        '3': ('LongTermBond', LongTermBondStrategy),
        '4': ('InverseETF', InverseETFStrategy),
        '5': ('FiftyFifty', FiftyFiftyStrategy),
        '6': ('ProportionalAllocation', ProportionalAllocationStrategy),
        '7': ('TSMCProportionalAllocation', TSMCProportionalAllocationStrategy)
    }
    
    strategy_name, strategy_class = strategy_map.get(strategy_choice, strategy_map['1'])
    
    # 設定日期範圍
    start_date = input("起始日期（YYYY-MM-DD，預設 2015-01-01）: ").strip()
    start_date = start_date if start_date else '2015-01-01'
    
    end_date = input("結束日期（YYYY-MM-DD，預設今天）: ").strip()
    end_date = end_date if end_date else datetime.now().strftime('%Y-%m-%d')
    
    # 初始資金
    capital = input("初始資金（預設 100,000）: ").strip()
    capital = int(capital) if capital.isdigit() else 100000
    
    print(f"\n[Info] 開始回測：{strategy_name} 策略")
    print(f"[Info] 日期範圍：{start_date} 至 {end_date}")
    print(f"[Info] 初始資金：{capital:,} 元")
    
    try:
        # 讀取景氣燈號資料
        print("\n[步驟 1] 讀取景氣燈號資料...")
        cycle_collector = CycleDataCollector('business_cycle/景氣指標與燈號.csv')
        cycle_data = cycle_collector.process_cycle_data(start_date, end_date)
        
        if cycle_data.empty:
            print("[Error] 無法讀取景氣燈號資料")
            return
        
        # 讀取股價資料
        print("\n[步驟 2] 讀取股價資料...")
        db_manager = DatabaseManager()
        
        start_date_str = start_date.replace('-', '')
        end_date_str = end_date.replace('-', '')
        
        # 取得需要的股票和ETF資料
        tickers = ['006208', '00865B', '00687B', '00664R', '2330']  # 新增台積電
        price_data_list = []
        
        for ticker in tickers:
            df = db_manager.get_stock_price(ticker=ticker, start_date=start_date_str, end_date=end_date_str)
            if not df.empty:
                price_data_list.append(df)
        
        if not price_data_list:
            print("[Error] 無法讀取股價資料，請先執行選項 2 蒐集資料")
            return
        
        price_data = pd.concat(price_data_list, ignore_index=True)
        print(f"[Info] 成功讀取 {len(price_data)} 筆股價資料")
        
        # 建立策略實例
        if strategy_name == 'Cash':
            strategy = strategy_class()
        else:
            strategy = strategy_class()
        
        # 定義策略函數
        def strategy_func(state, date, price_dict, positions=None, portfolio_value=None):
            return strategy.generate_orders(state, date, price_dict, positions, portfolio_value)
        
        # 執行回測
        print("\n[步驟 3] 執行回測...")
        engine = BacktestEngine(initial_capital=capital)
        results = engine.run_backtest(start_date, end_date, strategy_func, price_data, cycle_data)
        
        # 顯示結果
        print("\n" + "="*60)
        print("回測結果")
        print("="*60)
        print(f"最終價值：{results['final_value']:,.0f} 元")
        print(f"總報酬率：{results['total_return']*100:.2f}%")
        print(f"年化報酬率：{results['metrics']['annualized_return']*100:.2f}%")
        print(f"波動度：{results['metrics']['volatility']*100:.2f}%")
        print(f"夏普比率：{results['metrics']['sharpe_ratio']:.2f}")
        print(f"最大回落：{results['metrics']['max_drawdown']*100:.2f}%")
        print(f"總交易次數：{results['metrics']['total_trades']}")
        
    except Exception as e:
        print(f"[Error] 回測失敗: {e}")
        import traceback
        traceback.print_exc()


def generate_report():
    """選項 4：產生績效報告和圖表"""
    print("\n[選項 4] 產生績效報告和圖表")
    print("-" * 60)
    print("[Info] 此功能將在後續版本中實作")


def batch_update():
    """選項 5：批次更新資料"""
    print("\n[選項 5] 批次更新資料")
    print("-" * 60)
    
    start_date_input = input("請輸入起始日期（YYYY-MM-DD，預設 2015-01-01）: ").strip()
    start_date = start_date_input if start_date_input else '2015-01-01'
    start_date_compact = start_date.replace('-', '')
    days = 9999
    
    db_manager = DatabaseManager()
    collector = StockDataCollector(db_manager)
    
    fetch_otc = input("是否同時更新上櫃股票資料？(y/n，預設 y): ").strip().lower()
    if fetch_otc not in ('y', 'n'):
        fetch_otc = 'y'
    otc_collector = OTCDataCollector(db_manager) if fetch_otc == 'y' else None
    
    try:
        result = collector.batch_fetch_stock_prices_only(days=days, start_date=start_date_compact)
        print(f"\n[Info] 批次更新完成")
        print(f"成功：{result['success']} 天")
        print(f"失敗：{result['failed']} 天")
        print(f"跳過：{result['skipped']} 天")
        
        if fetch_otc == 'y' and otc_collector:
            otc_result = otc_collector.batch_fetch_otc_data(days=days, start_date=start_date_compact)
            print(f"\n[Info] 上櫃批次更新完成")
            print(f"成功：{otc_result['success']} 天")
            print(f"失敗：{otc_result['failed']} 天")
            print(f"跳過：{otc_result['skipped']} 天")
        
    except Exception as e:
        print(f"[Error] 批次更新失敗: {e}")
        import traceback
        traceback.print_exc()


def validate_data():
    """選項 6：驗證股價資料"""
    print("\n[選項 6] 驗證股價資料")
    print("-" * 60)
    
    validator = PriceValidator()
    
    # 輸入股票代號
    ticker_input = input("請輸入股票代號（多個請用逗號分隔，例如：006208,00865B）: ").strip()
    if not ticker_input:
        print("[Error] 請輸入股票代號")
        return
    
    tickers = [t.strip() for t in ticker_input.split(',')]
    
    # 輸入時間範圍
    start_date = input("請輸入起始日期（YYYY-MM-DD，預設：2015-01-01）: ").strip()
    if not start_date:
        start_date = '2015-01-01'
    
    end_date = input("請輸入結束日期（YYYY-MM-DD，預設：今天）: ").strip()
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    # 輸入檢查參數
    window_size_input = input("請輸入檢查窗口大小（天數，預設：5）: ").strip()
    window_size = int(window_size_input) if window_size_input.isdigit() else 5
    
    threshold_input = input("請輸入異常閾值（百分比，預設：20）: ").strip()
    try:
        threshold_pct = float(threshold_input) if threshold_input else 20.0
    except ValueError:
        threshold_pct = 20.0
    
    # 選擇市場
    market_input = input("請選擇市場（1=上市, 2=上櫃, 3=兩者，預設：3）: ").strip()
    market_map = {'1': 'listed', '2': 'otc', '3': 'both'}
    market = market_map.get(market_input, 'both')
    
    # 執行驗證
    print(f"\n開始驗證 {len(tickers)} 檔股票...")
    if len(tickers) == 1:
        anomalies = validator.validate_stock_price(tickers[0], start_date, end_date,
                                                   window_size, threshold_pct, market)
    else:
        anomalies = validator.validate_multiple_stocks(tickers, start_date, end_date,
                                                      window_size, threshold_pct, market)
    
    # 顯示結果
    validator.print_anomalies_report(anomalies)
    
    # 如果有異常，詢問是否刪除並重新蒐集
    if not anomalies.empty:
        # 詢問是否儲存報告
        save = input("\n是否儲存異常報告到 CSV？（y/n）: ").strip().lower()
        if save == 'y':
            filename = f"price_anomalies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            # 將列表轉換為字串以便儲存
            anomalies_save = anomalies.copy()
            anomalies_save['prev_prices'] = anomalies_save['prev_prices'].astype(str)
            anomalies_save['next_prices'] = anomalies_save['next_prices'].astype(str)
            anomalies_save.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"報告已儲存至: {filename}")
        
        # 詢問是否刪除異常資料並重新蒐集
        delete_and_recollect = input("\n是否刪除異常日期的資料並重新蒐集？（y/n）: ").strip().lower()
        if delete_and_recollect == 'y':
            print("\n[步驟 1] 刪除異常日期的資料...")
            delete_result = validator.delete_anomaly_data(anomalies)
            print(f"  已刪除 {delete_result['deleted']} 筆異常資料")
            if delete_result['errors']:
                print("  刪除過程中的錯誤：")
                for error in delete_result['errors']:
                    print(f"    - {error}")
            
            print("\n[步驟 2] 重新蒐集異常日期的資料...")
            recollect_result = validator.recollect_anomaly_data(anomalies)
            print(f"\n重新蒐集完成：")
            print(f"  成功重新蒐集 {recollect_result['recollected']} 筆資料")
            if recollect_result['errors']:
                print("  重新蒐集過程中的錯誤：")
                for error in recollect_result['errors']:
                    print(f"    - {error}")


def main():
    """主程式"""
    while True:
        print_menu()
        choice = input("\n請選擇功能（0-9）: ").strip()
        
        if choice == '0':
            print("\n[Info] 離開程式")
            break
        elif choice == '1':
            load_cycle_data()
        elif choice == '2':
            collect_stock_data()
        elif choice == '3':
            run_backtest()
        elif choice == '4':
            generate_report()
        elif choice == '5':
            batch_update()
        elif choice == '6':
            validate_data()
        elif choice == '7':
            check_data_integrity()
        elif choice == '8':
            fill_zero_price_data()
        elif choice == '9':
            delete_warrants_from_otc()
        else:
            print("[Error] 無效的選項，請重新選擇")
        
        input("\n按 Enter 繼續...")


def check_data_integrity():
    """選項 7：檢查資料完整性（檢查交易日是否有指定股票資料）"""
    print("\n[選項 7] 檢查資料完整性")
    print("-" * 60)
    
    from data_validation.price_validator import PriceValidator
    
    validator = PriceValidator()
    
    # 輸入要檢查的股票代號
    ticker = input("請輸入要檢查的股票代號（預設：006208）: ").strip()
    if not ticker:
        ticker = '006208'
    
    # 輸入時間範圍
    start_date = input("請輸入起始日期（YYYY-MM-DD，預設：2015-01-01）: ").strip()
    if not start_date:
        start_date = '2015-01-01'
    
    end_date = input("請輸入結束日期（YYYY-MM-DD，預設：今天）: ").strip()
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    # 執行檢查和修復
    result = validator.check_and_fix_missing_data(ticker, start_date, end_date)


def fill_zero_price_data():
    """選項 8：填補零值價格資料（處理沒有交易的日子）"""
    print("\n[選項 8] 填補零值價格資料")
    print("-" * 60)
    print("此功能會將零值價格資料（沒有交易的日子）填補為前一天的收盤價")
    print("volume 和 turnover 將設為 NULL，change 也會設為 NULL")
    print("-" * 60)
    
    validator = PriceValidator()
    
    # 選擇市場類型（需要先選擇，才知道要從哪個表查詢全部股票）
    print("\n請選擇市場類型：")
    print("1. 上市（個股和ETF）")
    print("2. 上櫃")
    print("3. 兩者都處理")
    market_choice = input("請選擇（1-3，預設：3）: ").strip()
    market_map = {'1': 'listed', '2': 'otc', '3': 'both'}
    market = market_map.get(market_choice, 'both')
    
    # 輸入股票代號（可多個，或按 Enter 處理全部）
    ticker_input = input("\n請輸入股票代號（多個請用逗號分隔，例如：006208,2330,00865B；直接按 Enter 處理全部股票）: ").strip()
    
    if not ticker_input:
        # 如果沒有輸入，從資料庫取得所有股票代號
        print("\n正在查詢資料庫中的所有股票代號...")
        db_manager = DatabaseManager()
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        all_tickers = set()
        
        if market in ['listed', 'both']:
            try:
                cursor.execute("SELECT DISTINCT ticker FROM tw_stock_price_data ORDER BY ticker")
                listed_tickers = [row[0] for row in cursor.fetchall()]
                all_tickers.update(listed_tickers)
                print(f"  上市市場: 找到 {len(listed_tickers)} 檔股票")
            except Exception as e:
                print(f"  [Warning] 查詢上市股票代號失敗: {e}")
        
        if market in ['otc', 'both']:
            try:
                cursor.execute("SELECT DISTINCT ticker FROM tw_otc_stock_price_data ORDER BY ticker")
                otc_tickers = [row[0] for row in cursor.fetchall()]
                all_tickers.update(otc_tickers)
                print(f"  上櫃市場: 找到 {len(otc_tickers)} 檔股票")
            except Exception as e:
                print(f"  [Warning] 查詢上櫃股票代號失敗: {e}")
        
        conn.close()
        
        tickers = sorted(list(all_tickers))
        
        if not tickers:
            print("[Error] 資料庫中沒有找到任何股票代號")
            return
        
        print(f"\n總共將處理 {len(tickers)} 檔股票")
        # 顯示前10個作為預覽
        if len(tickers) <= 10:
            print(f"股票代號: {', '.join(tickers)}")
        else:
            print(f"股票代號（前10個）: {', '.join(tickers[:10])} ...")
            print(f"共 {len(tickers)} 檔股票，將全部處理")
    else:
        tickers = [t.strip() for t in ticker_input.split(',') if t.strip()]
        if not tickers:
            print("[Error] 請輸入有效的股票代號")
            return
    
    # 輸入時間範圍（可選）
    print("\n時間範圍設定（直接按 Enter 表示處理全部資料）：")
    start_date_input = input("起始日期（YYYY-MM-DD，預設：全部）: ").strip()
    start_date = start_date_input if start_date_input else None
    
    end_date_input = input("結束日期（YYYY-MM-DD，預設：全部）: ").strip()
    end_date = end_date_input if end_date_input else None
    
    # 顯示處理資訊
    print(f"\n處理設定：")
    if len(tickers) <= 20:
        print(f"  股票代號: {', '.join(tickers)}")
    else:
        print(f"  股票代號（前20個）: {', '.join(tickers[:20])} ...")
        print(f"  共 {len(tickers)} 檔股票")
    print(f"  市場類型: {'上市' if market == 'listed' else '上櫃' if market == 'otc' else '上市+上櫃'}")
    if start_date or end_date:
        date_range = f"{start_date or '全部'} ~ {end_date or '全部'}"
        print(f"  時間範圍: {date_range}")
    else:
        print(f"  時間範圍: 全部資料")
    
    executed_any = False
    
    def print_result(title, result):
        print(f"\n{'='*60}")
        print(title)
        print(f"{'='*60}")
        print(f"總共填補: {result['filled']} 筆資料")
        if result['errors']:
            print(f"發生錯誤: {len(result['errors'])} 個")
            for error in result['errors'][:5]:
                print(f"  - {error}")
            if len(result['errors']) > 5:
                print(f"  ... 還有 {len(result['errors']) - 5} 個錯誤未顯示")
        if result.get('details'):
            print("\n詳細統計：")
            for key, detail in result['details'].items():
                market_ticker = key.split('_', 1)
                if len(market_ticker) == 2:
                    market_name = '上市' if market_ticker[0] == 'listed' else '上櫃'
                    ticker = market_ticker[1]
                    print(f"  {market_name} {ticker}: {detail['filled']} 筆")
        print(f"{'='*60}")
    
    zero_choice = input("\n是否執行「無成交零值填補」？（y/n，預設 y）: ").strip().lower()
    if zero_choice in ('', 'y'):
        executed_any = True
        print("\n開始執行無成交零值填補...")
        zero_result = validator.fill_zero_price_data(
            tickers=tickers,
            market=market,
            start_date=start_date,
            end_date=end_date
        )
        print_result("無成交零值填補完成", zero_result)
    else:
        print("[Info] 已跳過無成交零值填補")
    
    odd_choice = input("\n是否執行「零股成交但無整股價」填補？（y/n，預設 y）: ").strip().lower()
    if odd_choice in ('', 'y'):
        executed_any = True
        print("\n開始執行零股價格填補並標註 odd_lot_filled...")
        odd_result = validator.fill_odd_lot_price_data(
            tickers=tickers,
            market=market,
            start_date=start_date,
            end_date=end_date
        )
        print_result("零股價格填補完成", odd_result)
    else:
        print("[Info] 已跳過零股價格填補")
    
    if not executed_any:
        print("\n[Info] 未執行任何填補作業")


def delete_warrants_from_otc():
    """選項 9：刪除上櫃資料表中的權證資料"""
    print("\n[選項 9] 刪除上櫃資料表中的權證資料")
    print("-" * 60)
    print("此功能會刪除上櫃資料表中所有7開頭六位數的權證資料")
    print("例如：700071, 717441 等")
    print("-" * 60)
    
    # 先顯示會被刪除的權證數量
    validator = PriceValidator()
    db_manager = validator.db_manager
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    try:
        # 查詢權證種類和筆數
        cursor.execute("""
            SELECT COUNT(DISTINCT ticker) as count, COUNT(*) as records
            FROM tw_otc_stock_price_data
            WHERE ticker LIKE '7_____' 
              AND LENGTH(ticker) = 6
              AND ticker GLOB '[0-9]*'
        """)
        result = cursor.fetchone()
        warrant_tickers = result[0] if result else 0
        warrant_records = result[1] if result else 0
        
        if warrant_tickers == 0:
            print("\n✓ 資料庫中沒有找到權證資料")
            return
        
        print(f"\n預估將刪除：")
        print(f"  權證種類: {warrant_tickers} 種")
        print(f"  資料筆數: {warrant_records} 筆")
        
        # 顯示前10個權證代號作為預覽
        cursor.execute("""
            SELECT DISTINCT ticker
            FROM tw_otc_stock_price_data
            WHERE ticker LIKE '7_____' 
              AND LENGTH(ticker) = 6
              AND ticker GLOB '[0-9]*'
            ORDER BY ticker
            LIMIT 10
        """)
        preview_tickers = [row[0] for row in cursor.fetchall()]
        if preview_tickers:
            if warrant_tickers <= 10:
                print(f"  權證代號: {', '.join(preview_tickers)}")
            else:
                print(f"  權證代號（前10個）: {', '.join(preview_tickers)} ...")
        
    finally:
        conn.close()
    
    # 確認
    confirm = input("\n是否確認刪除？（輸入 'YES' 以確認）: ").strip()
    if confirm != 'YES':
        print("已取消操作")
        return
    
    # 執行刪除
    print("\n正在刪除權證資料...")
    result = validator.delete_warrants_from_otc()
    
    print(f"\n{'='*60}")
    print("刪除權證資料完成")
    print(f"{'='*60}")
    if 'errors' in result:
        print(f"[Error] 刪除過程發生錯誤")
        for error in result['errors']:
            print(f"  - {error}")
    else:
        if result.get('deleted', 0) > 0:
            print(f"已刪除 {result['deleted']} 筆權證資料")
        elif result.get('message'):
            print(result['message'])
    print(f"{'='*60}")


if __name__ == '__main__':
    main()

