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
from data_collection.indicator_data_collector import IndicatorDataCollector
from data_collection.stock_data_collector import StockDataCollector
from data_collection.otc_data_collector import OTCDataCollector
from backtesting.backtest_engine import BacktestEngine
from backtesting.strategy import (
    ShortTermBondStrategy, CashStrategy, LongTermBondStrategy,
    InverseETFStrategy, FiftyFiftyStrategy,
    ProportionalAllocationStrategy, TSMCProportionalAllocationStrategy,
    BuyAndHoldStrategy, M1BFilterCashStrategy, M1BFilterBondStrategy,
    M1BFilterProportionalStrategy, DynamicPositionCashStrategy,
    DynamicPositionBondStrategy, DynamicPositionProportionalStrategy,
    MultiplierAllocationCashStrategy, MultiplierAllocationBondStrategy
)
from data_validation.price_validator import PriceValidator


def print_menu():
    """顯示主選單"""
    print("\n" + "="*60)
    print("景氣週期投資策略系統")
    print("="*60)
    print("1. 讀取景氣燈號資料（從 CSV，驗證資料）")
    print("2. 蒐集股票和ETF資料（含禮貌休息）")
    print("3. 執行回測（2020 年至今）")
    print("4. 產生績效報告和圖表")
    print("5. 批次更新資料（含禮貌休息）")
    print("6. 驗證股價資料（檢查異常）")
    print("7. 檢查資料完整性（檢查交易日是否有指定股票資料）")
    print("8. 填補零值價格資料（處理沒有交易的日子）")
    print("9. 刪除上櫃資料表中的權證資料（7開頭六位數）")
    print("0. 離開")
    print("="*60)


def load_cycle_data():
    """選項 1：讀取景氣燈號與指標資料"""
    print("\n[選項 1] 讀取景氣燈號與指標資料")
    print("-" * 60)
    
    print("\n請選擇要匯入的資料：")
    print("1. 只匯入景氣燈號資料（business_cycle_data）")
    print("2. 匯入所有景氣指標資料（一鍵更新，包含 6 個資料表）")
    print("3. 選擇性匯入特定指標")
    
    choice = input("\n請選擇（1-3，預設 2）: ").strip()
    if not choice:
        choice = '2'
    
    # 設定日期範圍
    start_date = input("起始日期（YYYY-MM-DD，預設 2020-01-01）: ").strip()
    start_date = start_date if start_date else '2020-01-01'
    
    end_date = input("結束日期（YYYY-MM-DD，預設今天）: ").strip()
    end_date = end_date if end_date else datetime.now().strftime('%Y-%m-%d')
    
    db_manager = DatabaseManager()
    
    try:
        if choice == '1':
            # 只匯入景氣燈號資料（原有功能）
            csv_path = 'business_cycle/景氣指標與燈號.csv'
            collector = CycleDataCollector(csv_path)
            
            print(f"\n處理日期範圍：{start_date} 至 {end_date}")
            daily_df = collector.process_cycle_data(start_date, end_date)
            
            if daily_df.empty:
                print("[Error] 無法讀取景氣燈號資料")
                return
            
            print(f"\n[Info] 成功處理 {len(daily_df)} 筆交易日資料")
            print("\n前 5 筆資料：")
            print(daily_df[['date_str', 'score', 'val_shifted', 'signal']].head())
            
            # 儲存到資料庫
            collector.save_cycle_data_to_db(db_manager)
            print("[Info] 景氣燈號資料已儲存到資料庫")
            
        elif choice == '2':
            # 一鍵匯入所有景氣指標資料
            print(f"\n{'='*60}")
            print("一鍵匯入所有景氣指標資料")
            print(f"{'='*60}")
            print(f"處理日期範圍：{start_date} 至 {end_date}")
            
            # 初始化所有資料表
            print("\n[步驟 1] 初始化資料表...")
            db_manager.init_all_indicator_tables()
            
            # 匯入景氣燈號資料（business_cycle_data）
            print(f"\n[步驟 2] 匯入景氣燈號資料...")
            csv_path = 'business_cycle/景氣指標與燈號.csv'
            collector = CycleDataCollector(csv_path)
            daily_df = collector.process_cycle_data(start_date, end_date)
            if not daily_df.empty:
                collector.save_cycle_data_to_db(db_manager)
                print(f"[Success] 景氣燈號資料匯入成功，共 {len(daily_df)} 筆")
            else:
                print("[Warning] 景氣燈號資料為空")
            
            # 匯入所有其他指標資料
            print(f"\n[步驟 3] 匯入其他景氣指標資料...")
            indicator_collector = IndicatorDataCollector()
            results = indicator_collector.import_all_indicators(db_manager, start_date, end_date)
            
            # 顯示匯入結果統計
            print(f"\n{'='*60}")
            print("匯入結果統計")
            print(f"{'='*60}")
            success_count = sum(1 for r in results.values() if r.get('success', False))
            total_count = len(results)
            print(f"成功：{success_count}/{total_count} 個資料表")
            
            for csv_name, result in results.items():
                if result.get('success', False):
                    print(f"  ✓ {csv_name}: {result.get('records', 0)} 筆")
                else:
                    print(f"  ✗ {csv_name}: {result.get('error', '未知錯誤')}")
            
            # 計算 M1B 年增率（如果匯入了領先指標）
            leading_indicators_imported = False
            for csv_name, result in results.items():
                if csv_name == '領先指標構成項目.csv' and result.get('success', False):
                    leading_indicators_imported = True
                    break
            
            if leading_indicators_imported:
                print(f"\n[步驟 4] 計算 M1B 年增率...")
                from data_collection.m1b_calculator import M1BCalculator
                calculator = M1BCalculator()
                update_stats = calculator.calculate_and_update(db_manager)
                if update_stats.get('success'):
                    print(f"[Success] M1B 年增率計算完成")
                    print(f"  - 月對月年增率：更新 {update_stats.get('yoy_month_count', 0)} 筆")
                    print(f"  - 年增率動能：更新 {update_stats.get('yoy_momentum_count', 0)} 筆")
                    print(f"  - 月對月變化率：更新 {update_stats.get('mom_count', 0)} 筆")
                    print(f"  - 當月 vs 前三個月平均：更新 {update_stats.get('vs_3m_avg_count', 0)} 筆")
            
        elif choice == '3':
            # 選擇性匯入
            print("\n可選擇的指標：")
            print("1. 景氣燈號資料（business_cycle_data）")
            print("2. 領先指標構成項目")
            print("3. 同時指標構成項目")
            print("4. 落後指標構成項目")
            print("5. 景氣指標與燈號（綜合指標）")
            print("6. 景氣對策信號構成項目")
            
            selected = input("\n請選擇要匯入的項目（多個請用逗號分隔，例如：1,2,3）: ").strip()
            if not selected:
                print("[Info] 未選擇任何項目")
                return
            
            selected_list = [s.strip() for s in selected.split(',')]
            
            # 初始化所有資料表
            print("\n[步驟 1] 初始化資料表...")
            db_manager.init_all_indicator_tables()
            
            indicator_collector = IndicatorDataCollector()
            
            # 匯入選定的資料
            for sel in selected_list:
                if sel == '1':
                    # 景氣燈號資料
                    print(f"\n匯入景氣燈號資料...")
                    csv_path = 'business_cycle/景氣指標與燈號.csv'
                    collector = CycleDataCollector(csv_path)
                    daily_df = collector.process_cycle_data(start_date, end_date)
                    if not daily_df.empty:
                        collector.save_cycle_data_to_db(db_manager)
                        print(f"[Success] 景氣燈號資料匯入成功，共 {len(daily_df)} 筆")
                elif sel == '2':
                    result = indicator_collector.import_single_indicator('領先指標構成項目.csv', db_manager, start_date, end_date)
                    if result.get('success'):
                        print(f"[Success] 領先指標匯入成功，共 {result.get('records', 0)} 筆")
                        # 匯入成功後，立即計算 M1B 年增率
                        print("\n計算 M1B 年增率...")
                        from data_collection.m1b_calculator import M1BCalculator
                        calculator = M1BCalculator()
                        update_stats = calculator.calculate_and_update(db_manager)
                        if update_stats.get('success'):
                            print(f"[Success] M1B 年增率計算完成")
                            print(f"  - 月對月年增率：更新 {update_stats.get('yoy_month_count', 0)} 筆")
                            print(f"  - 年增率動能：更新 {update_stats.get('yoy_momentum_count', 0)} 筆")
                            print(f"  - 月對月變化率：更新 {update_stats.get('mom_count', 0)} 筆")
                            print(f"  - 當月 vs 前三個月平均：更新 {update_stats.get('vs_3m_avg_count', 0)} 筆")
                elif sel == '3':
                    result = indicator_collector.import_single_indicator('同時指標構成項目.csv', db_manager, start_date, end_date)
                    if result.get('success'):
                        print(f"[Success] 同時指標匯入成功，共 {result.get('records', 0)} 筆")
                elif sel == '4':
                    result = indicator_collector.import_single_indicator('落後指標構成項目.csv', db_manager, start_date, end_date)
                    if result.get('success'):
                        print(f"[Success] 落後指標匯入成功，共 {result.get('records', 0)} 筆")
                elif sel == '5':
                    result = indicator_collector.import_single_indicator('景氣指標與燈號.csv', db_manager, start_date, end_date)
                    if result.get('success'):
                        print(f"[Success] 綜合指標匯入成功，共 {result.get('records', 0)} 筆")
                elif sel == '6':
                    result = indicator_collector.import_single_indicator('景氣對策信號構成項目.csv', db_manager, start_date, end_date)
                    if result.get('success'):
                        print(f"[Success] 景氣對策信號構成項目匯入成功，共 {result.get('records', 0)} 筆")
        
        print("\n[Info] 所有資料匯入完成")
        
    except Exception as e:
        print(f"[Error] 匯入資料失敗: {e}")
        import traceback
        traceback.print_exc()


def collect_stock_data():
    """選項 2：蒐集股票和ETF資料"""
    print("\n[選項 2] 蒐集股票和ETF資料")
    print("-" * 60)
    
    # 詢問是否清除現有資料（從 2020 年重新蒐集）
    clear_data = input("是否清除現有資料並從 2020-01-01 重新蒐集？(y/n，預設 n): ").strip().lower()
    
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
            
            print("[Info] 資料清除完成，將從 2020-01-01 開始重新蒐集")
        else:
            print("[Info] 已取消清除資料操作")
            return
    
    # 詢問起始日期
    start_date_input = input("請輸入起始日期（YYYY-MM-DD，預設 2020-01-01）: ").strip()
    start_date = start_date_input if start_date_input else '2020-01-01'
    
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
    
    # 回測時間設定（允許自訂）
    print("\n回測時間範圍設定：")
    start_date_input = input("起始日期（YYYY-MM-DD，預設 2020-01-01）: ").strip()
    if not start_date_input:
        start_date = '2020-01-01'  # 預設起始日期
    else:
        # 驗證日期格式
        try:
            datetime.strptime(start_date_input, '%Y-%m-%d')
            start_date = start_date_input
        except ValueError:
            print("[Warning] 日期格式錯誤，使用預設日期 2020-01-01")
            start_date = '2020-01-01'
    
    end_date_input = input("結束日期（YYYY-MM-DD，預設今天）: ").strip()
    if not end_date_input:
        end_date = datetime.now().strftime('%Y-%m-%d')  # 預設為今天
    else:
        # 驗證日期格式
        try:
            datetime.strptime(end_date_input, '%Y-%m-%d')
            end_date = end_date_input
        except ValueError:
            print("[Warning] 日期格式錯誤，使用預設日期（今天）")
            end_date = datetime.now().strftime('%Y-%m-%d')
    
    # 驗證日期範圍合理性
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        if start_dt > end_dt:
            print("[Error] 起始日期不能晚於結束日期，已自動調整")
            start_date, end_date = end_date, start_date
    except ValueError:
        pass  # 日期格式已在上面驗證過
    
    # 初始資金
    capital = input("\n初始資金（預設 1,000,000）: ").strip()
    capital = int(capital) if capital.isdigit() else 1000000
    
    # 選擇執行模式
    print("\n請選擇執行模式：")
    print("1. 單一策略執行")
    print("2. 全部策略執行（包含基準策略）")
    
    mode_choice = input("請選擇（1-2，預設 1）: ").strip()
    if not mode_choice:
        mode_choice = '1'
    
    # 定義所有策略
    all_strategies = {
        '0': ('BuyAndHold', BuyAndHoldStrategy, '006208', None, None),  # 基準策略
        '1': ('ShortTermBond', ShortTermBondStrategy, '006208', '00865B', None),
        '2': ('Cash', CashStrategy, '006208', None, None),
        '3': ('LongTermBond', LongTermBondStrategy, '006208', '00687B', None),
        '4': ('InverseETF', InverseETFStrategy, '006208', '00664R', None),
        '5': ('FiftyFifty', FiftyFiftyStrategy, '006208', '00865B', None),
        '6': ('ProportionalAllocation', ProportionalAllocationStrategy, '006208', '00865B', None),
        '7': ('TSMCProportionalAllocation', TSMCProportionalAllocationStrategy, '2330', '00865B', None),
        '8': ('M1BFilterCash', M1BFilterCashStrategy, '006208', None, 'M1B動能濾網'),
        '9': ('M1BFilterBond', M1BFilterBondStrategy, '006208', '00865B', 'M1B動能濾網'),
        '10': ('M1BFilterProportional', M1BFilterProportionalStrategy, '006208', '00865B', 'M1B動能濾網'),
        '11': ('DynamicPositionCash', DynamicPositionCashStrategy, '006208', None, '動態倉位'),
        '12': ('DynamicPositionBond', DynamicPositionBondStrategy, '006208', '00865B', '動態倉位'),
        '13': ('DynamicPositionProportional', DynamicPositionProportionalStrategy, '006208', '00865B', '動態倉位'),
        '14': ('MultiplierAllocationCash', MultiplierAllocationCashStrategy, '006208', None, '倍數放大'),
        '15': ('MultiplierAllocationBond', MultiplierAllocationBondStrategy, '006208', '00865B', '倍數放大')
    }
    
    # 選擇要執行的策略
    if mode_choice == '1':
        # 單一策略執行
        print("\n請選擇策略：")
        print("0. 基準策略：買進並持有 006208")
        print("1. 短天期美債避險（主資產 006208）")
        print("2. 現金避險（主資產 006208）")
        print("3. 長天期美債避險（主資產 006208）")
        print("4. 反向ETF避險（主資產 006208）")
        print("5. 50:50配置（006208 + 短債）")
        print("6. 等比例配置（006208:短期美債）")
        print("7. 等比例配置（台積電:短期美債）")
        print("8. M1B 濾網 + 現金避險")
        print("9. M1B 濾網 + 短債避險")
        print("10. M1B 濾網 + 等比例配置")
        print("11. 動態倉位 + 現金避險")
        print("12. 動態倉位 + 短債避險")
        print("13. 動態倉位 + 等比例配置")
        print("14. 倍數放大 + 現金避險")
        print("15. 倍數放大 + 短債避險")
        
        strategy_choice = input("請選擇（0-15，預設 1）: ").strip()
        if not strategy_choice:
            strategy_choice = '1'
        
        selected_strategies = [strategy_choice]
    else:
        # 全部策略執行
        selected_strategies = list(all_strategies.keys())
    
    print(f"\n[Info] 回測時間：{start_date} 至 {end_date}")
    print(f"[Info] 初始資金：{capital:,} 元")
    print(f"[Info] 將執行 {len(selected_strategies)} 個策略")
    
    try:
        # 讀取景氣燈號資料
        print("\n[步驟 1] 讀取景氣燈號資料...")
        cycle_collector = CycleDataCollector('business_cycle/景氣指標與燈號.csv')
        cycle_data = cycle_collector.process_cycle_data(start_date, end_date)
        
        if cycle_data.empty:
            print("[Error] 無法讀取景氣燈號資料")
            return
        
        # 讀取 M1B 資料
        print("\n[步驟 1.5] 讀取 M1B 資料...")
        db_manager = DatabaseManager()
        start_date_str = start_date.replace('-', '')
        end_date_str = end_date.replace('-', '')
        
        m1b_query = """
            SELECT date, m1b_yoy_month, m1b_yoy_momentum, m1b_mom, m1b_vs_3m_avg
            FROM leading_indicators_data
            WHERE date >= ? AND date <= ?
            ORDER BY date
        """
        m1b_data = db_manager.execute_query_dataframe(m1b_query, (start_date_str, end_date_str))
        
        if m1b_data.empty:
            print("[Warning] 無法讀取 M1B 資料，部分策略可能無法正常運作")
            m1b_data = None
        else:
            print(f"[Info] 成功讀取 {len(m1b_data)} 筆 M1B 資料")
        
        # 讀取股價資料
        print("\n[步驟 2] 讀取股價資料...")
        tickers = ['006208', '00865B', '00687B', '00664R', '2330']
        price_data_list = []
        
        for ticker in tickers:
            # 先從上市資料表查詢
            df_listed = db_manager.get_stock_price(ticker=ticker, start_date=start_date_str, end_date=end_date_str)
            if not df_listed.empty:
                price_data_list.append(df_listed)
                print(f"[Info] 從上市市場讀取 {ticker}: {len(df_listed)} 筆")
            else:
                # 如果上市資料表沒有，再從上櫃資料表查詢
                df_otc = db_manager.get_otc_stock_price(ticker=ticker, start_date=start_date_str, end_date=end_date_str)
                if not df_otc.empty:
                    price_data_list.append(df_otc)
                    print(f"[Info] 從上櫃市場讀取 {ticker}: {len(df_otc)} 筆")
                else:
                    print(f"[Warning] {ticker} 在上市和上櫃市場都找不到資料")
        
        if not price_data_list:
            print("[Error] 無法讀取股價資料，請先執行選項 2 蒐集資料")
            return
        
        price_data = pd.concat(price_data_list, ignore_index=True)
        print(f"[Info] 成功讀取 {len(price_data)} 筆股價資料")
        
        # 執行所有選定的策略
        all_results = []
        
        for strategy_key in selected_strategies:
            if strategy_key not in all_strategies:
                continue
            
            strategy_name, strategy_class, stock_ticker, hedge_ticker, filter_name = all_strategies[strategy_key]
            
            print(f"\n[執行策略] {strategy_name}...")
            
            # 建立策略實例
            try:
                if strategy_name == 'BuyAndHold':
                    strategy = strategy_class(stock_ticker)
                elif strategy_name in ['Cash', 'M1BFilterCash', 'DynamicPositionCash', 'MultiplierAllocationCash']:
                    strategy = strategy_class(stock_ticker)
                elif strategy_name == 'TSMCProportionalAllocation':
                    strategy = strategy_class(stock_ticker, hedge_ticker)
                elif strategy_name in ['M1BFilterProportional', 'DynamicPositionProportional']:
                    # 這些策略需要特殊處理（多重繼承）
                    strategy = strategy_class(stock_ticker, hedge_ticker)
                elif hedge_ticker:
                    strategy = strategy_class(stock_ticker, hedge_ticker)
                else:
                    strategy = strategy_class(stock_ticker)
            except Exception as e:
                print(f"[Error] 建立策略 {strategy_name} 失敗: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # 定義策略函數
            def strategy_func(state, date, price_dict, positions=None, portfolio_value=None):
                return strategy.generate_orders(state, date, price_dict, positions, portfolio_value)
            
            # 執行回測
            engine = BacktestEngine(initial_capital=capital)
            results = engine.run_backtest(start_date, end_date, strategy_func, price_data, cycle_data, m1b_data)
            
            # 產生持倉變動摘要
            position_summary = engine.generate_position_summary()
            
            # 收集結果
            all_results.append({
                'strategy_name': strategy_name,
                'stock_ticker': stock_ticker,
                'hedge_ticker': hedge_ticker if hedge_ticker else 'null',
                'filter_name': filter_name if filter_name else 'null',
                'annualized_return': results['metrics']['annualized_return'] * 100,
                'total_return': results['total_return'] * 100,
                'volatility': results['metrics']['volatility'] * 100,
                'sharpe_ratio': results['metrics']['sharpe_ratio'],
                'max_drawdown': results['metrics']['max_drawdown'] * 100,
                'turnover_rate': results['metrics'].get('turnover_rate', 0),
                'avg_holding_period': results['metrics'].get('avg_holding_period', 0),
                'win_rate': results['metrics'].get('win_rate', 0),
                'total_trades': results['metrics']['total_trades'],
                'position_summary': position_summary,
                'trades': results['trades'],
                'final_value': results.get('final_value', capital),
                'initial_capital': capital
            })
        
        # 輸出結果到 CSV
        print("\n[步驟 3] 產生結果表格...")
        export_results_to_csv(all_results, start_date, end_date)
        
        # 顯示摘要結果
        print("\n" + "="*60)
        print("回測結果摘要")
        print("="*60)
        print(f"{'策略名稱':<25} {'年化報酬率':<12} {'累積報酬率':<12} {'夏普值':<8} {'最大回撤':<10}")
        print("-" * 60)
        for result in all_results:
            print(f"{result['strategy_name']:<25} {result['annualized_return']:>10.2f}% {result['total_return']:>10.2f}% {result['sharpe_ratio']:>6.2f} {result['max_drawdown']:>8.2f}%")
        
    except Exception as e:
        print(f"[Error] 回測失敗: {e}")
        import traceback
        traceback.print_exc()


def export_results_to_csv(all_results, start_date, end_date):
    """輸出回測結果到 CSV 檔案"""
    import os
    
    # 確保輸出目錄存在
    output_dir = '策略結果'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 產生檔案名稱
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = os.path.join(output_dir, f'backtest_results_{timestamp}.csv')
    
    # 準備資料
    rows = []
    for result in all_results:
        position_summary = result['position_summary']
        row = {
            '策略名稱': result['strategy_name'],
            '資產標的': result['stock_ticker'],
            '避險資產': result['hedge_ticker'],
            '濾網名稱': result['filter_name'],
            '初始資金': f"{result.get('initial_capital', 0):,.0f}",
            '最終資產總額': f"{result.get('final_value', 0):,.0f}",
            '年化報酬率(%)': f"{result['annualized_return']:.2f}",
            '累積報酬率(%)': f"{result['total_return']:.2f}",
            '波動度(%)': f"{result['volatility']:.2f}",
            '夏普值': f"{result['sharpe_ratio']:.2f}",
            '最大回撤(%)': f"{result['max_drawdown']:.2f}",
            '換手率(%)': f"{result['turnover_rate']:.2f}",
            '平均持倉期間(天)': f"{result['avg_holding_period']:.1f}",
            '勝率(%)': f"{result['win_rate']:.2f}",
            '總交易次數': result['total_trades'],
            '買進次數': position_summary['buy_trades'],
            '賣出次數': position_summary['sell_trades'],
            '最長持倉期間(天)': position_summary['max_holding_period'],
            '最短持倉期間(天)': position_summary['min_holding_period']
        }
        rows.append(row)
    
    # 建立 DataFrame 並輸出
    df_results = pd.DataFrame(rows)
    df_results.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    
    print(f"[Success] 結果已輸出至: {csv_filename}")
    
    # 同時輸出持倉變動詳細列表（如果交易次數不多）
    for result in all_results:
        if result['total_trades'] > 0 and result['total_trades'] <= 1000:  # 只輸出交易次數較少的策略
            trades_filename = os.path.join(output_dir, f'position_changes_{result["strategy_name"]}_{timestamp}.csv')
            trades_df = pd.DataFrame(result['trades'])
            # 將日期轉換為字串格式以便 CSV 輸出
            if 'date' in trades_df.columns:
                trades_df['date'] = trades_df['date'].astype(str)
            trades_df.to_csv(trades_filename, index=False, encoding='utf-8-sig')
            print(f"[Info] {result['strategy_name']} 持倉變動詳細列表已輸出至: {trades_filename}")


def generate_report():
    """選項 4：產生績效報告和圖表"""
    print("\n[選項 4] 產生績效報告和圖表")
    print("-" * 60)
    print("[Info] 此功能將在後續版本中實作")


def batch_update():
    """選項 5：批次更新資料"""
    print("\n[選項 5] 批次更新資料")
    print("-" * 60)
    
    start_date_input = input("請輸入起始日期（YYYY-MM-DD，預設 2020-01-01）: ").strip()
    start_date = start_date_input if start_date_input else '2020-01-01'
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
    start_date = input("請輸入起始日期（YYYY-MM-DD，預設：2020-01-01）: ").strip()
    if not start_date:
        start_date = '2020-01-01'
    
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
    start_date = input("請輸入起始日期（YYYY-MM-DD，預設：2020-01-01）: ").strip()
    if not start_date:
        start_date = '2020-01-01'
    
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

