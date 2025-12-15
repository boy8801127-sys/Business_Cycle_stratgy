"""
景氣週期投資策略主執行檔
提供互動式選單和主要功能入口
"""

import os
import sys
import json
import time
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

# 策略名稱縮寫對照表（用於 Excel 工作表命名）
STRATEGY_NAME_MAP = {
    'BuyAndHold': 'BuyHold',
    'ShortTermBond': 'ST_Bond',
    'Cash': 'Cash',
    'LongTermBond': 'LT_Bond',
    'InverseETF': 'InvETF',
    'FiftyFifty': '50_50',
    'OrangePrediction': 'Orange',
}


def _get_ticker_names(tickers):
    """
    從資料庫取得股票名稱對照表
    
    參數:
    - tickers: 股票代號列表，例如 ['006208', '00865B', '00687B']
    
    返回:
    - dict: {ticker: stock_name}
    """
    db_manager = DatabaseManager()
    ticker_names = {}
    
    for ticker in tickers:
        if not ticker or ticker == 'null':
            continue
        # 先從上市市場查詢
        query = """
            SELECT DISTINCT stock_name 
            FROM tw_stock_price_data 
            WHERE ticker = ? AND stock_name IS NOT NULL AND stock_name != ''
            LIMIT 1
        """
        result = db_manager.execute_query(query, (ticker,))
        if result:
            ticker_names[ticker] = result[0][0]
        else:
            # 如果上市市場沒有，從上櫃市場查詢
            query = """
                SELECT DISTINCT stock_name 
                FROM tw_otc_stock_price_data 
                WHERE ticker = ? AND stock_name IS NOT NULL AND stock_name != ''
                LIMIT 1
            """
            result = db_manager.execute_query(query, (ticker,))
            if result:
                ticker_names[ticker] = result[0][0]
            else:
                ticker_names[ticker] = ticker  # 如果找不到，使用代號
    
    return ticker_names


def _merge_daily_and_trades(dates, portfolio_values, returns, trades, ticker_names, daily_positions=None, daily_cash=None):
    """
    合併每日數據與交易記錄
    
    參數:
    - dates: 日期列表
    - portfolio_values: 投資組合價值列表
    - returns: 每日報酬率列表
    - trades: 交易記錄列表
    - ticker_names: 股票名稱對照表
    - daily_positions: 每日持倉記錄列表 [{ticker: shares}, ...]
    - daily_cash: 每日現金餘額列表
    
    返回:
    - DataFrame: 合併後的數據
    """
    # 建立日期索引的交易記錄字典
    trades_by_date = {}
    for trade in trades:
        trade_date = trade.get('日期')
        if trade_date is None:
            continue
        
        # 標準化日期格式
        if isinstance(trade_date, str):
            try:
                trade_date = pd.to_datetime(trade_date).date()
            except:
                continue
        elif hasattr(trade_date, 'date'):
            trade_date = trade_date.date()
        
        if trade_date not in trades_by_date:
            trades_by_date[trade_date] = []
        trades_by_date[trade_date].append(trade)
    
    # 輔助函數：將日期轉換為字串格式
    def format_date_for_excel(date_val):
        """將日期轉換為 'YYYY-MM-DD' 字串格式，方便 Power BI 讀取"""
        if date_val is None:
            return ''
        if isinstance(date_val, str):
            # 如果已經是字串，嘗試解析後再格式化
            try:
                date_obj = pd.to_datetime(date_val)
                return date_obj.strftime('%Y-%m-%d')
            except:
                return date_val
        elif hasattr(date_val, 'strftime'):
            # datetime 或 date 對象
            return date_val.strftime('%Y-%m-%d')
        elif hasattr(date_val, 'date'):
            # datetime 對象
            return date_val.date().strftime('%Y-%m-%d')
        else:
            return str(date_val)
    
    # 合併數據
    merged_data = []
    if returns:
        returns_series = pd.Series(returns).fillna(0)
        cumulative_returns = (1 + returns_series).cumprod().sub(1).mul(100)
    else:
        cumulative_returns = pd.Series([0] * len(dates))
    
    # 追蹤持倉平均成本 {ticker: {'shares': int, 'avg_cost': float, 'total_cost': float}}
    positions_cost = {}
    
    for i, date in enumerate(dates):
        date_obj = date
        # 標準化日期格式（用於比對交易記錄）
        if isinstance(date, str):
            try:
                date_obj = pd.to_datetime(date).date()
            except:
                continue
        elif hasattr(date, 'date'):
            date_obj = date.date()
        
        # 格式化日期為字串（用於輸出到 Excel）
        date_str = format_date_for_excel(date)
        
        # 取得當日持倉
        day_positions = daily_positions[i] if daily_positions and i < len(daily_positions) else {}
        
        # 取得當日現金餘額
        cash_balance = daily_cash[i] if daily_cash and i < len(daily_cash) else None
        
        # 每天只建立一行（合併同一天的所有交易）
        row = {
            '日期': date_str,
            '投資組合價值': round(portfolio_values[i], 2) if i < len(portfolio_values) else None,
            '每日報酬率(%)': round(returns[i] * 100, 4) if returns and i < len(returns) and returns[i] is not None else None,
            '累積報酬率(%)': round(cumulative_returns.iloc[i], 2) if i < len(cumulative_returns) else None,
            '持倉': '',  # 先設為空，處理完交易後再格式化（包含平均成本）
            '現金部位': round(cash_balance, 2) if cash_balance is not None else None,
            '動作': '',
            '總交易量(價格)': 0,
            '盈虧': 0,
            '稅費': 0
        }
        
        # 如果這一天有交易，合併所有交易資訊
        if date_obj in trades_by_date:
            trades_today = trades_by_date[date_obj]
            actions = []
            buy_total = 0
            sell_total = 0
            buy_fees = 0  # 買進手續費
            sell_fees = 0  # 賣出證交稅
            daily_profit_loss = 0  # 當天的盈虧
            
            # 先處理買進交易（更新持倉成本），再處理賣出交易（計算盈虧）
            buy_trades = [t for t in trades_today if t.get('動作') == '買進']
            sell_trades = [t for t in trades_today if t.get('動作') == '賣出']
            
            # 處理買進：更新持倉平均成本
            for trade in buy_trades:
                ticker = trade.get('標的代號', '')
                shares = trade.get('股數', 0) or 0
                price = trade.get('價格', 0) or 0
                trade_amount = shares * price
                fee = trade.get('手續費', 0) or 0
                
                # 累積動作和金額
                asset_name = ticker_names.get(ticker, ticker)
                actions.append(f"買進{asset_name}")
                buy_total += trade_amount
                buy_fees += fee
                
                # 更新持倉平均成本（加權平均）
                if ticker in positions_cost:
                    # 加權平均：(舊總成本 + 新成本) / (舊股數 + 新股數)
                    old_shares = positions_cost[ticker]['shares']
                    old_total_cost = positions_cost[ticker]['total_cost']
                    new_total_cost = old_total_cost + trade_amount
                    new_total_shares = old_shares + shares
                    positions_cost[ticker]['shares'] = new_total_shares
                    positions_cost[ticker]['total_cost'] = new_total_cost
                    positions_cost[ticker]['avg_cost'] = new_total_cost / new_total_shares if new_total_shares > 0 else 0
                else:
                    # 第一次買進
                    positions_cost[ticker] = {
                        'shares': shares,
                        'avg_cost': price,
                        'total_cost': trade_amount
                    }
            
            # 處理賣出：計算實現損益
            for trade in sell_trades:
                ticker = trade.get('標的代號', '')
                shares = trade.get('股數', 0) or 0
                price = trade.get('價格', 0) or 0
                trade_amount = shares * price
                tax = trade.get('證交稅', 0) or 0
                
                # 累積動作和金額
                asset_name = ticker_names.get(ticker, ticker)
                actions.append(f"賣出{asset_name}")
                sell_total += trade_amount
                sell_fees += tax
                
                # 計算實現損益（使用當前持倉的平均成本）
                if ticker in positions_cost and positions_cost[ticker]['shares'] > 0:
                    avg_cost = positions_cost[ticker]['avg_cost']
                    cost_basis = shares * avg_cost  # 賣出的成本基礎
                    net_revenue = trade_amount - tax  # 賣出淨收入
                    realized_pnl = net_revenue - cost_basis  # 實現損益
                    daily_profit_loss += realized_pnl
                    
                    # 更新持倉（減少股數，平均成本不變）
                    positions_cost[ticker]['shares'] -= shares
                    if positions_cost[ticker]['shares'] <= 0:
                        # 全部賣完，清除持倉
                        positions_cost[ticker]['shares'] = 0
                        positions_cost[ticker]['total_cost'] = 0
                        positions_cost[ticker]['avg_cost'] = 0
                    else:
                        # 按比例減少總成本
                        positions_cost[ticker]['total_cost'] = positions_cost[ticker]['shares'] * avg_cost
                else:
                    # 沒有持倉記錄，無法計算成本基礎，只計算淨收入
                    net_revenue = trade_amount - tax
                    daily_profit_loss += net_revenue
            
            # 扣除買進手續費（作為費用）
            daily_profit_loss -= buy_fees
            
            # 合併動作（用分號分隔）
            row['動作'] = '；'.join(actions)
            row['總交易量(價格)'] = round(buy_total + sell_total, 2)
            row['盈虧'] = round(daily_profit_loss, 2)
            row['稅費'] = round(buy_fees + sell_fees, 2)
        
        # 處理完交易後，格式化持倉字串（包含平均成本）
        # 使用當日持倉和更新後的 positions_cost
        position_str_parts = []
        for ticker, shares in sorted(day_positions.items()):
            if shares > 0:
                # 取得平均成本
                # 注意：day_positions 是當日結束時的持倉，positions_cost 是處理完交易後的持倉
                # 理論上應該一致，但為了安全，優先使用 positions_cost 中的股數來取得平均成本
                avg_cost = None
                if ticker in positions_cost:
                    # 如果 positions_cost 中有記錄，使用其平均成本
                    # 即使 shares 為 0，也可能有平均成本記錄（剛賣完的情況）
                    if positions_cost[ticker]['shares'] > 0:
                        # 有持倉，使用平均成本
                        avg_cost = positions_cost[ticker]['avg_cost']
                    elif positions_cost[ticker].get('avg_cost', 0) > 0:
                        # 沒有持倉但還有平均成本記錄（剛賣完），使用最後的平均成本
                        avg_cost = positions_cost[ticker]['avg_cost']
                
                # 格式化：ticker:shares@avg_cost
                # 使用 day_positions 中的股數（當日實際持倉），但平均成本從 positions_cost 取得
                if avg_cost is not None and avg_cost > 0:
                    position_str_parts.append(f"{ticker}:{shares}@{round(avg_cost, 2)}")
                else:
                    # 如果沒有平均成本記錄，只顯示股數
                    position_str_parts.append(f"{ticker}:{shares}")
        row['持倉'] = ';'.join(position_str_parts) if position_str_parts else ''
        
        merged_data.append(row)
    
    return pd.DataFrame(merged_data)
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
    print("3. 執行回測（2020 年至今）[已捨棄]")
    print("4. 產生績效報告和圖表")
    print("5. 批次更新資料（含禮貌休息）")
    print("6. 驗證股價資料（檢查異常）")
    print("7. 檢查資料完整性（檢查交易日是否有指定股票資料）")
    print("8. 填補零值價格資料（處理沒有交易的日子）")
    print("9. 刪除上櫃資料表中的權證資料（7開頭六位數）")
    print("10. 更新專案說明文件（自動檢測變更並更新）")
    print("-" * 60)
    print("11. 輸出 Orange 分析數據（股價 + 指標數據）")
    print("12. 執行回測（新系統，基於 Orange 資料）")
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


def update_project_docs():
    """更新專案說明文件"""
    print("\n[更新專案說明文件]")
    print("-" * 60)
    
    try:
        # 導入更新腳本
        import sys
        import importlib.util
        from pathlib import Path
        
        scripts_path = Path(__file__).parent / 'scripts' / 'update_project_context.py'
        if scripts_path.exists():
            spec = importlib.util.spec_from_file_location("update_project_context", scripts_path)
            if spec and spec.loader:
                update_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(update_module)
                if hasattr(update_module, 'main'):
                    update_module.main()
                else:
                    print("[Warning] 更新腳本缺少 main 函數")
            else:
                print("[Warning] 無法載入更新腳本")
        else:
            print("[Warning] 找不到更新腳本，請手動執行 scripts/update_project_context.py")
    except Exception as e:
        print(f"[Error] 更新失敗: {e}")
        import traceback
        traceback.print_exc()


def run_backtest_new():
    """選項 12：執行回測（新系統，基於 Orange 資料）"""
    print("\n[選項 12] 執行回測（新系統，基於 Orange 資料）")
    print("-" * 60)
    
    # 檢查 Orange 資料檔案是否存在
    csv_path = 'results/orange_analysis_data.csv'
    if not os.path.exists(csv_path):
        print(f"[Error] 找不到 Orange 資料檔案：{csv_path}")
        print("       請先執行選項 11 產生 Orange 分析數據")
        return
    
    # 回測時間設定（固定為 2020-01-01 至 2025-11-30）
    start_date = '2020-01-01'
    end_date = '2025-11-30'
    print(f"\n回測時間範圍：{start_date} 至 {end_date}")
    
    # 初始資金
    capital = input("\n初始資金（預設 1,000,000）: ").strip()
    capital = int(capital) if capital.isdigit() else 1000000
    
    # 匯入新的回測引擎和策略
    from backtesting.backtest_engine_new import BacktestEngineNew
    from backtesting.strategy_new import (
        BuyAndHoldStrategyNew, 
        ShortTermBondStrategyNew,
        CashStrategyNew,
        LongTermBondStrategyNew,
        InverseETFStrategyNew,
        FiftyFiftyStrategyNew
    )
    
    # [Orange 相關功能] 條件匯入 Orange 預測策略（可選依賴）
    ORANGE_AVAILABLE = False
    OrangePredictionStrategy = None
    try:
        from backtesting.strategy_orange import OrangePredictionStrategy
        ORANGE_AVAILABLE = True
    except ImportError as e:
        print(f"[Orange Warning] Orange 預測策略不可用: {e}")
        print(f"[Orange Info] 策略 2（Orange 預測策略）將不會出現在選單中")
    except Exception as e:
        print(f"[Orange Warning] 載入 Orange 預測策略時發生錯誤: {e}")
    
    # 定義所有策略（基本策略）
    all_strategies = {
        '0': ('BuyAndHold', BuyAndHoldStrategyNew, '006208', None, None),
        '1': ('ShortTermBond', ShortTermBondStrategyNew, '006208', '00865B', None),
    }
    
    # 新增四個策略（編號固定為 '3' 到 '6'，因為 Orange 佔據 '2'）
    all_strategies['3'] = ('Cash', CashStrategyNew, '006208', None, None)
    all_strategies['4'] = ('LongTermBond', LongTermBondStrategyNew, '006208', '00687B', None)
    all_strategies['5'] = ('InverseETF', InverseETFStrategyNew, '006208', '00664R', None)
    all_strategies['6'] = ('FiftyFifty', FiftyFiftyStrategyNew, '006208', '00865B', None)
    
    # [Orange 相關功能] 條件性加入 Orange 預測策略（保持在 '2'）
    # 注意：這個條件判斷必須在新增四個策略之後執行
    if ORANGE_AVAILABLE and OrangePredictionStrategy is not None:
        all_strategies['2'] = ('OrangePrediction', OrangePredictionStrategy, '006208', '00865B', None)
    
    # 選擇執行模式
    print("\n請選擇執行模式：")
    strategy_count = len(all_strategies)
    print(f"1. 單一策略執行")
    print(f"2. 全部策略執行（目前有 {strategy_count} 個策略）")
    
    mode_choice = input("請選擇（1-2，預設 1）: ").strip()
    if not mode_choice:
        mode_choice = '1'
    
    # 選擇要執行的策略
    if mode_choice == '1':
        # 單一策略執行
        print("\n請選擇策略：")
        print("0. 基準策略：買進並持有 006208")
        print("1. 短天期美債避險（主資產 006208）")
        
        # [Orange 相關功能] 條件性顯示 Orange 預測策略選項
        if ORANGE_AVAILABLE and OrangePredictionStrategy is not None:
            print("2. Orange 預測策略（主資產 006208）[需要 Orange 模型]")
        
        # 新增的四個策略（固定編號 3-6）
        print("3. 現金避險（主資產 006208）")
        print("4. 長天期美債避險（主資產 006208）")
        print("5. 反向ETF避險（主資產 006208）")
        print("6. 50:50配置（主資產 006208）")
        
        # 動態計算策略範圍
        # 如果 Orange 可用，範圍是 0-6；如果不可用，範圍是 0,1,3-6（跳過 2）
        if ORANGE_AVAILABLE and OrangePredictionStrategy is not None:
            strategy_range = "0-6"  # 包含 Orange (2)
        else:
            strategy_range = "0,1,3-6"  # 跳過 2（Orange 不可用）
        
        strategy_choice = input(f"請選擇（{strategy_range}，預設 1）: ").strip()
        if not strategy_choice:
            strategy_choice = '1'
        
        # 驗證選擇的策略是否存在
        if strategy_choice not in all_strategies:
            print(f"[Error] 無效的策略選擇: {strategy_choice}")
            if not ORANGE_AVAILABLE and strategy_choice == '2':
                print("[Info] Orange 預測策略不可用，請選擇其他策略")
            return
        
        selected_strategies = [strategy_choice]
    else:
        # 全部策略執行（排除 Orange 策略）
        selected_strategies = [key for key in all_strategies.keys() if key != '2']
        print(f"[Info] 將執行 {len(selected_strategies)} 個策略（已排除 Orange 預測策略）")
    
    print(f"\n[Info] 回測時間：{start_date} 至 {end_date}")
    print(f"[Info] 初始資金：{capital:,} 元")
    print(f"[Info] 將執行 {len(selected_strategies)} 個策略")
    
    try:
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
                elif strategy_name == 'OrangePrediction':
                    # [Orange 相關功能] Orange 預測策略需要模型路徑
                    model_path = 'orange_data_export/tree.pkcls'
                    strategy = strategy_class(stock_ticker, hedge_ticker, model_path)
                elif strategy_name == 'Cash':
                    # Cash Strategy 沒有 hedge_ticker
                    strategy = strategy_class(stock_ticker)
                elif hedge_ticker:
                    # 其他有避險資產的策略
                    strategy = strategy_class(stock_ticker, hedge_ticker)
                else:
                    strategy = strategy_class(stock_ticker)
            except Exception as e:
                print(f"[Error] 建立策略 {strategy_name} 失敗: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # 檢查 OrangePredictionStrategy 的模型載入狀態
            if strategy_name == 'OrangePrediction':
                if hasattr(strategy, 'model_available') and not strategy.model_available:
                    error_msg = getattr(strategy, 'load_error', '未知錯誤')
                    print(f"[Error] Orange 策略模型載入失敗，跳過此策略: {error_msg}")
                    continue
            
            # 定義策略函數
            def strategy_func(state, date, row, price_dict, positions=None, portfolio_value=None):
                return strategy.generate_orders(state, date, row, price_dict, positions, portfolio_value)
            
            # 取得策略需要的標的列表
            strategy_tickers = [stock_ticker]
            if hedge_ticker:
                strategy_tickers.append(hedge_ticker)
            
            # 執行回測
            engine = BacktestEngineNew(initial_capital=capital)
            results = engine.run_backtest(start_date, end_date, strategy_func, tickers=strategy_tickers)
            
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
                'total_trades': results['metrics']['total_trades'],
                'position_summary': position_summary,
                'trades': results['trades'],
                'final_value': results.get('final_value', capital),
                'initial_capital': capital,
                'final_positions': results.get('final_positions', {}),
                'final_cash': results.get('final_cash', 0),
                # 每日報酬率數據
                'dates': results['dates'],
                'portfolio_value': results['portfolio_value'],
                'returns': results['returns'],
                # 每日持倉記錄
                'daily_positions': results.get('daily_positions', []),
                # 每日現金餘額記錄
                'daily_cash': results.get('daily_cash', [])
            })
            
            print(f"[Info] {strategy_name} 回測完成")
            print(f"  總報酬率: {results['total_return']*100:.2f}%")
            print(f"  年化報酬率: {results['metrics']['annualized_return']*100:.2f}%")
            print(f"  最大回撤: {results['metrics']['max_drawdown']*100:.2f}%")
            print(f"  夏普比率: {results['metrics']['sharpe_ratio']:.2f}")
            print(f"  交易次數: {results['metrics']['total_trades']}")
        
        if not all_results:
            print("[Error] 沒有策略執行成功")
            return
        
        # 檢查 openpyxl 是否已安裝
        try:
            import openpyxl
        except ImportError:
            print("[Error] 需要安裝 openpyxl 才能輸出 Excel 檔案")
            print("       請執行: pip install openpyxl")
            return
        
        # 輸出結果到 Excel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 建立結果目錄
        results_dir = 'results'
        os.makedirs(results_dir, exist_ok=True)
        
        # 收集所有用到的 ticker
        all_tickers = set()
        for r in all_results:
            if r['stock_ticker']:
                all_tickers.add(r['stock_ticker'])
            if r['hedge_ticker']:
                all_tickers.add(r['hedge_ticker'])
        
        # 取得股票名稱對照表
        print("\n[步驟 1] 取得股票名稱對照表...")
        ticker_names = _get_ticker_names(list(all_tickers))
        
        # 建立摘要 DataFrame（第一張工作表）
        summary_df = pd.DataFrame([
            {
                '策略名稱': r['strategy_name'],
                '股票代號': r['stock_ticker'],
                '避險資產': r['hedge_ticker'] if r['hedge_ticker'] else '無',
                '總報酬率(%)': round(r['total_return'], 2),
                '年化報酬率(%)': round(r['annualized_return'], 2),
                '波動率(%)': round(r['volatility'], 2),
                '夏普比率': round(r['sharpe_ratio'], 2),
                '最大回撤(%)': round(r['max_drawdown'], 2),
                '交易次數': r['total_trades'],
                '最終價值': round(r['final_value'], 2),
                '最終現金': round(r['final_cash'], 2)
            }
            for r in all_results
        ])
        
        # 建立 Excel 檔案
        excel_path = f'{results_dir}/backtest_results_new_{timestamp}.xlsx'
        print(f"\n[步驟 2] 輸出 Excel 檔案：{excel_path}")
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # 第一張工作表：策略摘要
            summary_df.to_excel(writer, sheet_name='策略摘要', index=False)
            
            # 為每個策略建立工作表
            for r in all_results:
                strategy_name = r['strategy_name']
                sheet_name = STRATEGY_NAME_MAP.get(strategy_name, strategy_name[:31])
                
                # 合併每日數據與交易記錄
                if r['dates'] and r['portfolio_value'] and r['returns']:
                    # 確保 daily_positions 存在且長度正確
                    daily_positions = r.get('daily_positions', [])
                    
                    if not daily_positions or len(daily_positions) != len(r['dates']):
                        # 如果 daily_positions 不存在或長度不匹配，使用空列表
                        print(f"[Warning] {strategy_name} 策略的 daily_positions 不存在或長度不匹配（daily_positions: {len(daily_positions) if daily_positions else 0}, dates: {len(r['dates'])}），使用空列表")
                        daily_positions = [{}] * len(r['dates']) if r['dates'] else []
                    
                    # 取得每日現金餘額
                    daily_cash = r.get('daily_cash')
                    
                    if not daily_cash or len(daily_cash) != len(r['dates']):
                        # 如果 daily_cash 不存在或長度不匹配，使用 None
                        daily_cash = None
                    
                    merged_df = _merge_daily_and_trades(
                        r['dates'], 
                        r['portfolio_value'], 
                        r['returns'], 
                        r['trades'],
                        ticker_names,
                        daily_positions,  # 傳入每日持倉記錄
                        daily_cash  # 傳入每日現金餘額
                    )
                    
                    # 寫入數據（直接從第1行開始）
                    merged_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    print(f"      - 工作表 '{sheet_name}' 已建立（{len(merged_df)} 筆記錄）")
                else:
                    # 如果沒有每日數據，建立空的工作表
                    empty_df = pd.DataFrame(columns=['日期', '投資組合價值', '每日報酬率(%)', '累積報酬率(%)', 
                                                     '動作', '總交易量(價格)', '盈虧', '稅費'])
                    empty_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    print(f"      - 工作表 '{sheet_name}' 已建立（無數據）")
        
        print(f"\n[Info] Excel 檔案已輸出：{excel_path}")
        print(f"       包含 {len(all_results) + 1} 個工作表（1 個摘要 + {len(all_results)} 個策略）")
        
        print("\n[完成] 所有回測結果已輸出")
        
    except Exception as e:
        print(f"\n[Error] 回測失敗: {e}")
        import traceback
        traceback.print_exc()


def export_orange_data():
    """選項 11：輸出 Orange 分析數據"""
    try:
        # 導入輸出腳本
        import sys
        import importlib.util
        from pathlib import Path
        
        scripts_path = Path(__file__).parent / 'scripts' / 'export_orange_data.py'
        if scripts_path.exists():
            spec = importlib.util.spec_from_file_location("export_orange_data", scripts_path)
            if spec and spec.loader:
                export_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(export_module)
                if hasattr(export_module, 'export_orange_data'):
                    export_module.export_orange_data()
                else:
                    print("[Error] 輸出腳本缺少 export_orange_data 函數")
            else:
                print("[Error] 無法載入輸出腳本")
        else:
            print("[Error] 找不到輸出腳本 scripts/export_orange_data.py")
    except Exception as e:
        print(f"[Error] 輸出失敗: {e}")
        import traceback
        traceback.print_exc()


def run_backtest():
    """選項 3：執行回測"""
    print("\n[選項 3] 執行回測")
    
    # 檢查是否需要更新專案說明文件
    try:
        import importlib.util
        from pathlib import Path
        
        scripts_path = Path(__file__).parent / 'scripts' / 'update_project_context.py'
        if scripts_path.exists():
            spec = importlib.util.spec_from_file_location("update_project_context", scripts_path)
            if spec and spec.loader:
                update_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(update_module)
                if hasattr(update_module, 'check_file_changes'):
                    changes = update_module.check_file_changes()
                    if changes:
                        print(f"\n[Info] 檢測到 {len(changes)} 個關鍵檔案變更，建議更新專案說明文件")
                        print("       （可在選單中選擇更新選項）")
    except Exception as e:
        # 如果檢查失敗，不影響回測執行
        pass
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
                'initial_capital': capital,
                'final_positions': results.get('final_positions', {}),  # 新增
                'final_cash': results.get('final_cash', 0),  # 新增
                # 新增：每日報酬率數據
                'dates': results.get('dates', []),
                'portfolio_value': results.get('portfolio_value', []),
                'returns': results.get('returns', [])
            })
        
        # 輸出結果到 CSV
        print("\n[步驟 3] 產生結果表格...")
        export_results_to_csv(all_results, start_date, end_date)
        
        # 診斷LongTermBond策略問題
        print("\n[步驟 4] 診斷LongTermBond策略...")
        diagnose_strategy(all_results, 'LongTermBond')
        
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


def diagnose_strategy(all_results, strategy_name):
    """診斷特定策略的問題"""
    import os
    
    strategy_result = None
    for result in all_results:
        if result['strategy_name'] == strategy_name:
            strategy_result = result
            break
    
    if not strategy_result:
        return
    
    print(f"\n{'='*60}")
    print(f"診斷策略：{strategy_name}")
    print(f"{'='*60}")
    
    # 基本資訊
    print(f"初始資金：{strategy_result.get('initial_capital', 0):,.0f}")
    print(f"最終資產總額：{strategy_result.get('final_value', 0):,.0f}")
    print(f"累積報酬率：{strategy_result.get('total_return', 0):.2f}%")
    print(f"最大回撤：{strategy_result.get('max_drawdown', 0):.2f}%")
    print(f"總交易次數：{strategy_result.get('total_trades', 0)}")
    
    # 檢查交易記錄
    trades = strategy_result.get('trades', [])
    if trades:
        print(f"\n交易記錄分析：")
        
        # 檢查異常價格
        abnormal_trades = []
        for trade in trades:
            ticker = trade.get('ticker')
            price = trade.get('price', 0)
            action = trade.get('action')
            
            if price <= 0:
                abnormal_trades.append({
                    'date': trade.get('date'),
                    'ticker': ticker,
                    'action': action,
                    'price': price,
                    'reason': '價格為0或負數'
                })
        
        if abnormal_trades:
            print(f"  發現 {len(abnormal_trades)} 筆異常價格交易：")
            for abnormal in abnormal_trades[:5]:  # 只顯示前5筆
                date_str = str(abnormal['date']) if abnormal['date'] else 'N/A'
                print(f"    {date_str} {abnormal['ticker']} {abnormal['action']} @ {abnormal['price']} - {abnormal['reason']}")
            if len(abnormal_trades) > 5:
                print(f"    ... 還有 {len(abnormal_trades) - 5} 筆異常交易")
        
        # 檢查價格波動
        ticker_prices = {}
        for trade in trades:
            ticker = trade.get('ticker')
            if ticker not in ticker_prices:
                ticker_prices[ticker] = []
            ticker_prices[ticker].append(trade.get('price', 0))
        
        print(f"\n  價格範圍分析：")
        for ticker, prices in ticker_prices.items():
            if prices:
                valid_prices = [p for p in prices if p > 0]
                if valid_prices:
                    min_price = min(valid_prices)
                    max_price = max(valid_prices)
                    avg_price = sum(valid_prices) / len(valid_prices)
                    max_change_pct = ((max_price - min_price) / avg_price * 100) if avg_price > 0 else 0
                    print(f"    {ticker}: 最低={min_price:.2f}, 最高={max_price:.2f}, 平均={avg_price:.2f}, 波動範圍={max_change_pct:.2f}%")
                    
                    # 檢查是否有極端波動
                    if max_change_pct > 50:
                        print(f"      ⚠️  警告：{ticker} 價格波動超過50%")
        
        # 檢查是否有重複交易
        trade_dates = {}
        for trade in trades:
            date = trade.get('date')
            ticker = trade.get('ticker')
            action = trade.get('action')
            key = (date, ticker, action)
            if key not in trade_dates:
                trade_dates[key] = 0
            trade_dates[key] += 1
        
        duplicate_trades = [(k, v) for k, v in trade_dates.items() if v > 1]
        if duplicate_trades:
            print(f"\n  發現 {len(duplicate_trades)} 筆重複交易：")
            for (date, ticker, action), count in duplicate_trades[:5]:
                date_str = str(date) if date else 'N/A'
                print(f"    {date_str} {ticker} {action} 重複 {count} 次")
    
    # 比較與其他類似策略
    if strategy_name == 'LongTermBond':
        short_term_result = None
        for result in all_results:
            if result['strategy_name'] == 'ShortTermBond':
                short_term_result = result
                break
        
        if short_term_result:
            print(f"\n與ShortTermBond策略比較：")
            print(f"  LongTermBond累積報酬率：{strategy_result.get('total_return', 0):.2f}%")
            print(f"  ShortTermBond累積報酬率：{short_term_result.get('total_return', 0):.2f}%")
            diff = strategy_result.get('total_return', 0) - short_term_result.get('total_return', 0)
            print(f"  差異：{diff:.2f}%")
            if abs(diff) > 10:
                print(f"  ⚠️  警告：兩個策略表現差異超過10%，可能避險資產選擇有問題")
    
    # 輸出詳細交易記錄到CSV（如果交易次數合理）
    if len(trades) > 0 and len(trades) <= 500:
        output_dir = 'results'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        diagnostic_filename = os.path.join(output_dir, f'diagnostic_{strategy_name}_{timestamp}.csv')
        
        trades_df = pd.DataFrame(trades)
        if 'date' in trades_df.columns:
            trades_df['date'] = trades_df['date'].astype(str)
        trades_df.to_csv(diagnostic_filename, index=False, encoding='utf-8-sig')
        print(f"\n  詳細交易記錄已輸出至：{diagnostic_filename}")
    
    print(f"{'='*60}\n")


def export_results_to_csv(all_results, start_date, end_date):
    """輸出回測結果到 CSV 檔案"""
    import os
    
    # 確保輸出目錄存在
    output_dir = 'results'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 產生檔案名稱
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = os.path.join(output_dir, f'backtest_results_{timestamp}.csv')
    
    # 準備資料
    rows = []
    for result in all_results:
        position_summary = result['position_summary']
        
        # 處理最終持倉資訊
        final_positions = result.get('final_positions', {})
        positions_str = ""
        if final_positions:
            position_items = []
            for ticker, pos_info in final_positions.items():
                position_items.append(f"{ticker}: {pos_info['shares']:.0f}股 @ {pos_info['price']:.2f} = {pos_info['value']:,.0f}")
            positions_str = "; ".join(position_items)
        else:
            positions_str = "無持倉"
        
        row = {
            '策略名稱': result['strategy_name'],
            '資產標的': result['stock_ticker'],
            '避險資產': result['hedge_ticker'],
            '濾網名稱': result['filter_name'],
            '初始資金': f"{result.get('initial_capital', 0):,.0f}",
            '最終資產總額': f"{result.get('final_value', 0):,.0f}",
            '最終現金': f"{result.get('final_cash', 0):,.0f}",
            '最終持倉': positions_str,  # 新增
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
            if '日期' in trades_df.columns:
                trades_df['日期'] = trades_df['日期'].astype(str)
            
            # 格式化數值欄位到小數點第二位（股數保持整數）
            numeric_columns = ['股數', '價格', '成本', '手續費', '總成本', 
                             '收入', '證交稅', '淨收入', 'M1B年增率', 
                             'M1B年增率動能', 'M1B動能', 'M1Bvs3月平均', 
                             '目標持倉比例', '目標股票比例', '目標債券比例',
                             '燈號年份', '燈號月份', '燈號分數']
            for col in numeric_columns:
                if col in trades_df.columns:
                    if col == '股數':
                        # 股數保持整數
                        trades_df[col] = trades_df[col].astype(int)
                    else:
                        # 其他數值四捨五入到小數點第二位
                        trades_df[col] = trades_df[col].round(2)
            
            trades_df.to_csv(trades_filename, index=False, encoding='utf-8-sig')
            print(f"[Info] {result['strategy_name']} 持倉變動詳細列表已輸出至: {trades_filename}")
    
    # 同時輸出每日報酬率（如果有的話）
    for result in all_results:
        if result.get('dates') and result.get('portfolio_value') and result.get('returns'):
            # 建立每日報酬率 DataFrame
            daily_returns_data = {
                '日期': [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in result['dates']],
                '投資組合價值': [round(v, 2) for v in result['portfolio_value']],
                '每日報酬率(%)': [round(r * 100, 4) for r in result['returns']],  # 轉換為百分比
                '累積報酬率(%)': []
            }
            
            # 計算累積報酬率
            initial_value = result['portfolio_value'][0] if result['portfolio_value'] else result.get('initial_capital', 1000000)
            for pv in result['portfolio_value']:
                cumulative_return = (pv / initial_value - 1) * 100
                daily_returns_data['累積報酬率(%)'].append(round(cumulative_return, 2))
            
            daily_returns_df = pd.DataFrame(daily_returns_data)
            daily_returns_filename = os.path.join(output_dir, f'daily_returns_{result["strategy_name"]}_{timestamp}.csv')
            daily_returns_df.to_csv(daily_returns_filename, index=False, encoding='utf-8-sig')
            print(f"[Info] {result['strategy_name']} 每日報酬率已輸出至: {daily_returns_filename}")


def generate_report():
    """選項 4：產生績效報告和圖表"""
    print("\n[選項 4] 產生績效報告和圖表")
    print("-" * 60)
    
    # 檢查是否有回測結果
    results_dir = "results"
    if not os.path.exists(results_dir):
        print("[Error] 找不到回測結果目錄，請先執行回測")
        return
    
    # 讀取回測結果
    print("\n[步驟 1] 讀取回測結果...")
    all_results = {}
    
    # 尋找最新的回測結果目錄（排除 "charts" 目錄）
    result_dirs = [d for d in os.listdir(results_dir) 
                   if os.path.isdir(os.path.join(results_dir, d)) and d != 'charts']
    
    # 如果沒有子目錄，直接在根目錄尋找 CSV
    if not result_dirs:
        # CSV 檔案直接在根目錄
        result_path = results_dir
        print("[Info] 在回測結果根目錄尋找 CSV 檔案")
    else:
        # 讓用戶選擇要使用的回測結果
        print("\n可用的回測結果：")
        for i, dir_name in enumerate(result_dirs, 1):
            print(f"  {i}. {dir_name}")
        print(f"  {len(result_dirs) + 1}. 使用根目錄的 CSV 檔案")
        
        choice = input("\n請選擇要使用的回測結果（輸入編號，預設使用最新的）: ").strip()
        if choice and choice.isdigit():
            choice_num = int(choice)
            if choice_num == len(result_dirs) + 1:
                result_path = results_dir
            else:
                selected_dir = result_dirs[choice_num - 1]
                result_path = os.path.join(results_dir, selected_dir)
        else:
            # 使用最新的（按修改時間排序）
            selected_dir = max(result_dirs, key=lambda d: os.path.getmtime(os.path.join(results_dir, d)))
            print(f"[Info] 使用最新的回測結果：{selected_dir}")
            result_path = os.path.join(results_dir, selected_dir)
    
    # 讀取所有策略的 CSV 檔案（修正檔案命名模式：支援 position_changes_*.csv）
    csv_files = [f for f in os.listdir(result_path) 
                 if f.endswith('.csv') and ('position_changes_' in f or '_trades.csv' in f)]
    
    if not csv_files:
        print("[Error] 找不到交易記錄 CSV 檔案")
        print(f"[Info] 在目錄 {result_path} 中尋找檔案")
        print(f"[Info] 預期的檔案格式：position_changes_*.csv 或 *_trades.csv")
        return
    
    print(f"[Info] 找到 {len(csv_files)} 個策略的交易記錄")
    
    # 讀取資料庫資料
    print("\n[步驟 2] 讀取資料庫資料...")
    db_manager = DatabaseManager()
    
    # 讀取股價資料
    stock_tickers = ['006208', '00865B', '2330']  # 常用的標的
    price_data_list = []
    for ticker in stock_tickers:
        # 使用與回測相同的格式讀取股價資料
        start_date_str = '20200101'
        end_date_str = datetime.now().strftime('%Y%m%d')
        
        # 先從上市市場查詢
        df = db_manager.get_stock_price(ticker=ticker, start_date=start_date_str, end_date=end_date_str)
        if df.empty:
            # 如果上市市場沒有，再從上櫃市場查詢
            df = db_manager.get_otc_stock_price(ticker=ticker, start_date=start_date_str, end_date=end_date_str)
        
        if not df.empty:
            # 確保有 ticker 欄位
            if 'ticker' not in df.columns:
                df['ticker'] = ticker
            price_data_list.append(df)
    
    if not price_data_list:
        print("[Error] 無法讀取股價資料")
        return
    
    price_data = pd.concat(price_data_list, ignore_index=True)
    
    # 確保日期格式正確
    if 'date' in price_data.columns:
        # 如果 date 是字串格式 YYYYMMDD，轉換為 date 對象
        if isinstance(price_data['date'].iloc[0], str) and len(str(price_data['date'].iloc[0])) == 8:
            price_data['date'] = pd.to_datetime(price_data['date'], format='%Y%m%d').dt.date
        else:
            price_data['date'] = pd.to_datetime(price_data['date']).dt.date
    
    # 讀取景氣燈號資料
    cycle_collector = CycleDataCollector('business_cycle/景氣指標與燈號.csv')
    cycle_data = cycle_collector.process_cycle_data('2020-01-01', datetime.now().strftime('%Y-%m-%d'))
    
    if cycle_data.empty:
        print("[Error] 無法讀取景氣燈號資料")
        return
    
    # 讀取 M1B 資料（如果有）
    m1b_data = None
    try:
        indicator_collector = IndicatorDataCollector()
        m1b_data = indicator_collector.get_m1b_data('2020-01-01', datetime.now().strftime('%Y-%m-%d'))
    except:
        print("[Warning] 無法讀取 M1B 資料，將跳過 M1B 相關圖表")
    
    # 讀取回測結果（從 CSV 重建結果字典）
    print("\n[步驟 3] 重建回測結果...")
    
    # 讀取 backtest_results_*.csv 獲取策略績效指標
    backtest_csv_files = [f for f in os.listdir(result_path) if f.startswith('backtest_results_')]
    if not backtest_csv_files:
        print("[Error] 找不到回測結果 CSV 檔案（backtest_results_*.csv）")
        return
    
    # 使用最新的回測結果 CSV
    latest_backtest_csv = max(backtest_csv_files, key=lambda f: os.path.getmtime(os.path.join(result_path, f)))
    print(f"[Info] 讀取回測結果檔案：{latest_backtest_csv}")
    
    df_results = pd.read_csv(os.path.join(result_path, latest_backtest_csv), encoding='utf-8-sig')
    
    # 為每個策略建立結果字典
    for _, row in df_results.iterrows():
        strategy_name = row['策略名稱']
        
        # 讀取對應的交易記錄 CSV
        position_csv = f"position_changes_{strategy_name}_{latest_backtest_csv.replace('backtest_results_', '')}"
        position_csv_path = os.path.join(result_path, position_csv)
        
        trades = []
        dates = []
        
        if os.path.exists(position_csv_path):
            # 讀取交易記錄
            df_trades = pd.read_csv(position_csv_path, encoding='utf-8-sig')
            
            # 轉換日期格式
            if '日期' in df_trades.columns:
                df_trades['日期'] = pd.to_datetime(df_trades['日期']).dt.date
                dates = sorted(df_trades['日期'].unique().tolist())
            
            # 轉換交易記錄為字典列表
            trades = df_trades.to_dict('records')
        
        # 解析數值（處理可能包含逗號、引號和百分號的格式）
        def parse_value(value):
            if pd.isna(value):
                return 0.0
            if isinstance(value, str):
                # 移除引號、逗號和百分號
                value = value.replace('"', '').replace(',', '').replace('%', '').strip()
            try:
                return float(value)
            except:
                return 0.0
        
        # 建立結果字典
        all_results[strategy_name] = {
            'metrics': {
                'total_return': parse_value(row.get('累積報酬率(%)', 0)) / 100,
                'annualized_return': parse_value(row.get('年化報酬率(%)', 0)) / 100,
                'sharpe_ratio': parse_value(row.get('夏普值', 0)),
                'max_drawdown': parse_value(row.get('最大回撤(%)', 0)) / 100,
                'volatility': parse_value(row.get('波動度(%)', 0)) / 100,
                'total_trades': int(parse_value(row.get('總交易次數', 0))),
                'turnover_rate': parse_value(row.get('換手率(%)', 0)),
                'avg_holding_period': parse_value(row.get('平均持倉期間(天)', 0)),
                'win_rate': parse_value(row.get('勝率(%)', 0)) / 100
            },
            'trades': trades,
            'dates': dates,
            'portfolio_value': []  # 需要從交易記錄計算，暫時為空
        }
        
        print(f"[Info] 已載入策略：{strategy_name}（{len(trades)} 筆交易記錄）")
    
    print(f"[Info] 共載入 {len(all_results)} 個策略的回測結果")
    
    # 計算投資組合價值歷史（簡化版本：從交易記錄和股價資料計算）
    print("\n[步驟 3.5] 計算投資組合價值歷史...")
    for strategy_name, result in all_results.items():
        if not result['trades'] or not result['dates']:
            continue
        
        # 從交易記錄計算投資組合價值
        # 這是一個簡化版本，實際應該模擬完整的回測過程
        # 這裡我們使用初始資金和最終資產總額來估算
        initial_capital_str = df_results[df_results['策略名稱'] == strategy_name]['初始資金'].iloc[0]
        final_value_str = df_results[df_results['策略名稱'] == strategy_name]['最終資產總額'].iloc[0]
        
        initial_capital = parse_value(initial_capital_str)
        final_value = parse_value(final_value_str)
        
        # 計算投資組合價值歷史
        # 方法：從交易記錄和股價資料重建投資組合價值
        if result['dates'] and result['trades']:
            try:
                # 建立日期到價格的映射
                price_dict_by_date = {}
                for ticker in stock_tickers:
                    ticker_data = price_data[price_data['ticker'] == ticker].copy()
                    if not ticker_data.empty:
                        ticker_data['date'] = pd.to_datetime(ticker_data['date']).dt.date
                        for _, row in ticker_data.iterrows():
                            date = row['date']
                            if date not in price_dict_by_date:
                                price_dict_by_date[date] = {}
                            price_dict_by_date[date][ticker] = row['close']
                
                # 模擬投資組合價值變化
                portfolio_values = []
                positions = {}  # {ticker: shares}
                cash = initial_capital
                
                # 按日期排序交易記錄
                sorted_trades = sorted(result['trades'], key=lambda t: t.get('日期', datetime.min.date()))
                
                # 建立所有日期的完整列表（從第一個交易日到最後一個交易日）
                if result['dates']:
                    all_dates = sorted(result['dates'])
                    # 如果交易記錄中有更多日期，也要包含
                    trade_dates = [t.get('日期') for t in sorted_trades if t.get('日期')]
                    all_dates = sorted(set(all_dates + [d for d in trade_dates if d]))
                    
                    trade_idx = 0
                    for date in all_dates:
                        # 處理這一天的所有交易
                        while trade_idx < len(sorted_trades):
                            trade = sorted_trades[trade_idx]
                            trade_date = trade.get('日期')
                            if trade_date and trade_date <= date:
                                # 執行交易
                                ticker = trade.get('標的代號', '')
                                action = trade.get('動作', '')
                                
                                if action == '買進':
                                    shares = trade.get('股數', 0)
                                    price = trade.get('價格', 0)
                                    total_cost = trade.get('總成本', shares * price)
                                    if total_cost <= cash:
                                        cash -= total_cost
                                        positions[ticker] = positions.get(ticker, 0) + shares
                                elif action == '賣出':
                                    shares = trade.get('股數', 0)
                                    price = trade.get('價格', 0)
                                    net_proceeds = trade.get('淨收入', shares * price * 0.9967)  # 扣除手續費和稅
                                    if ticker in positions:
                                        positions[ticker] = max(0, positions[ticker] - shares)
                                        if positions[ticker] == 0:
                                            del positions[ticker]
                                    cash += net_proceeds
                                
                                trade_idx += 1
                            else:
                                break
                        
                        # 計算當天的投資組合價值
                        portfolio_value = cash
                        if date in price_dict_by_date:
                            for ticker, shares in positions.items():
                                if ticker in price_dict_by_date[date]:
                                    portfolio_value += shares * price_dict_by_date[date][ticker]
                        portfolio_values.append(portfolio_value)
                    
                    result['portfolio_value'] = portfolio_values
                    result['dates'] = all_dates
                else:
                    result['portfolio_value'] = [initial_capital]
            except Exception as e:
                print(f"[Warning] 計算 {strategy_name} 投資組合價值時發生錯誤：{e}")
                # 使用簡化版本
                if result['dates']:
                    num_days = len(result['dates'])
                    if num_days > 1:
                        daily_return = (final_value / initial_capital) ** (1.0 / num_days) - 1
                        portfolio_values = []
                        current_value = initial_capital
                        for _ in result['dates']:
                            portfolio_values.append(current_value)
                            current_value *= (1 + daily_return)
                        result['portfolio_value'] = portfolio_values
                    else:
                        result['portfolio_value'] = [initial_capital, final_value]
                else:
                    result['portfolio_value'] = [initial_capital]
        else:
            result['portfolio_value'] = [initial_capital]
    
    # 選擇輸出格式
    print("\n請選擇輸出格式：")
    print("1. PNG（靜態圖表）")
    print("2. HTML（互動式圖表）")
    print("3. 兩者都生成")
    
    format_choice = input("\n請選擇（1-3，預設 3）: ").strip()
    format_map = {'1': 'png', '2': 'html', '3': 'both'}
    output_format = format_map.get(format_choice, 'both')
    
    # 生成圖表
    print("\n[步驟 4] 生成圖表...")
    try:
        from backtesting.chart_generator import ChartGenerator
        
        # 創建圖表生成器
        chart_gen = ChartGenerator(all_results, price_data, cycle_data, m1b_data)
        
        # 生成所有策略比較圖表
        chart_gen.generate_all_strategies_comparison(result_path, format=output_format)
        
        print("\n[Info] 圖表生成完成！")
        print(f"[Info] 圖表儲存位置：{result_path}")
        
    except Exception as e:
        print(f"[Error] 生成圖表時發生錯誤：{e}")
        import traceback
        traceback.print_exc()


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
        try:
            print_menu()
            choice = input("\n請選擇功能（0-11）: ").strip()
            
            # 過濾掉可能的 PowerShell 自動執行腳本或路徑
            # 如果輸入看起來像腳本路徑或命令，視為無效
            if not choice or len(choice) > 10:
                # 選項應該是 0-10，長度不應該超過 2 個字符
                if len(choice) > 10:
                    print("[Error] 無效的選項，請重新選擇")
                    continue
                # 空輸入時跳過
                if not choice:
                    continue
            
            # 檢查是否包含路徑分隔符或腳本副檔名（可能是 PowerShell 自動執行）
            if '\\' in choice or '/' in choice or '.ps1' in choice.lower() or '.bat' in choice.lower() or choice.startswith('&'):
                print("[Error] 無效的選項，請重新選擇")
                print("[Info] 請直接輸入數字（0-10），不要輸入路徑或命令")
                continue
            
            # 只接受數字
            if not choice.isdigit():
                print("[Error] 無效的選項，請輸入數字（0-12）")
                continue
            
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
            elif choice == '10':
                update_project_docs()
            elif choice == '11':
                export_orange_data()
            elif choice == '12':
                run_backtest_new()
            else:
                print("[Error] 無效的選項，請輸入 0-12 之間的數字")
            
            input("\n按 Enter 繼續...")
        except (EOFError, KeyboardInterrupt):
            print("\n\n[Info] 程式已中斷")
            break
        except Exception as e:
            print(f"\n[Error] 發生未預期的錯誤: {e}")
            import traceback
            traceback.print_exc()
            try:
                input("\n按 Enter 繼續...")
            except:
                break


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

