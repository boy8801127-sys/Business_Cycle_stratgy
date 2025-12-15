"""
新的景氣週期投資策略回測引擎
基於資料庫資料（已對齊 n-2 個月指標）
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import json
import sys
import time
import math

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collection.database_manager import DatabaseManager


class BacktestEngineNew:
    """新的景氣週期投資策略回測引擎（基於 Orange 資料）"""
    
    def __init__(self, initial_capital=1000000, commission_rate=0.001425, tax_rate=0.003):
        """
        初始化回測引擎
        
        參數:
        - initial_capital: 初始資金（預設 1,000,000 元）
        - commission_rate: 手續費率（預設 0.1425%）
        - tax_rate: 證交稅率（預設 0.3%，賣出時）
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate
        
        # 回測狀態
        self.cash = initial_capital
        self.positions = {}  # {ticker: shares}
        self.portfolio_value = []  # 每日投資組合價值
        self.returns = []  # 每日報酬率
        self.trades = []  # 交易記錄
        self.dates = []  # 日期列表
        self.daily_positions = []  # 每日持倉記錄 [{ticker: shares}, ...]
        self.daily_cash = []  # 每日現金餘額記錄
        
        # 缺失價格警告追蹤
        self._missing_price_warnings = []
    
    def calculate_commission(self, value):
        """計算手續費"""
        commission = value * self.commission_rate
        return max(commission, 20)  # 最低 20 元
    
    def calculate_tax(self, value):
        """計算證交稅（賣出時）"""
        return value * self.tax_rate
    
    def load_data(self, tickers, start_date, end_date):
        """
        從資料庫載入資料
        
        參數:
        - tickers: 要讀取的標的列表（例如 ['006208', '00865B']）
        - start_date: 起始日期（date 對象或 'YYYY-MM-DD' 字串）
        - end_date: 結束日期（date 對象或 'YYYY-MM-DD' 字串）
        
        返回:
        - DataFrame: 處理好的資料
        """
        # 轉換日期格式
        if isinstance(start_date, str):
            start_date = pd.Timestamp(start_date).date()
        if isinstance(end_date, str):
            end_date = pd.Timestamp(end_date).date()
        
        # 轉換為資料庫格式（YYYYMMDD）
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')
        
        print(f"[Info] 正在從資料庫載入資料：{start_date_str} 至 {end_date_str}")
        print(f"[Info] 標的：{tickers}")
        
        # 初始化資料庫管理器
        db_manager = DatabaseManager()
        
        # 1. 讀取股票和避險資產價格資料
        stock_df = self._load_stock_data_from_db(db_manager, tickers, start_date_str, end_date_str)
        
        if stock_df.empty:
            raise ValueError(f"無法從資料庫讀取標的資料：{tickers}")
        
        # 2. 讀取指標資料
        indicator_df = self._load_indicator_data_from_db(db_manager)
        
        if indicator_df.empty:
            raise ValueError("無法從資料庫讀取指標資料")
        
        # 3. 對齊指標資料（n-2個月）
        df = self._align_indicators(stock_df, indicator_df)
        
        # 過濾掉 ticker 為 None 的資料
        df = df[df['ticker'].notna()].copy()
        
        # 按 ticker 和 date 排序
        df = df.sort_values(['ticker', 'date']).reset_index(drop=True)
        
        print(f"[Info] 成功載入 {len(df)} 筆資料")
        valid_dates = df['date'].dropna()
        if len(valid_dates) > 0:
            print(f"[Info] 日期範圍：{valid_dates.min()} 至 {valid_dates.max()}")
        valid_tickers = [t for t in df['ticker'].unique() if t is not None]
        if valid_tickers:
            print(f"[Info] 股票代號：{sorted(valid_tickers)}")
        
        return df
    
    def _load_stock_data_from_db(self, db_manager, tickers, start_date_str, end_date_str):
        """
        從資料庫讀取股票和避險資產價格資料
        
        參數:
        - db_manager: DatabaseManager 實例
        - tickers: 標的列表
        - start_date_str: 起始日期（YYYYMMDD）
        - end_date_str: 結束日期（YYYYMMDD）
        
        返回:
        - DataFrame: 股票價格資料
        """
        stock_data_list = []
        
        for ticker in tickers:
            if not ticker:
                continue
            
            print(f"  讀取 {ticker}...")
            
            # 嘗試從上市股票資料表讀取
            df = db_manager.get_stock_price(
                ticker=ticker,
                start_date=start_date_str,
                end_date=end_date_str
            )
            
            # 如果上市股票沒有資料，嘗試從上櫃股票資料表讀取
            if df.empty:
                df = db_manager.get_otc_stock_price(
                    ticker=ticker,
                    start_date=start_date_str,
                    end_date=end_date_str
                )
            
            if not df.empty:
                # 轉換日期格式
                df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.date
                # 標準化 ticker 格式
                df['ticker'] = df['ticker'].apply(self._normalize_ticker)
                # 只保留需要的欄位
                df = df[['date', 'ticker', 'close']].copy()
                stock_data_list.append(df)
        
        if not stock_data_list:
            return pd.DataFrame()
        
        # 合併所有標的的資料
        stock_df = pd.concat(stock_data_list, ignore_index=True)
        stock_df = stock_df.sort_values(['date', 'ticker']).reset_index(drop=True)
        
        print(f"  共讀取 {len(stock_df)} 筆股價數據")
        
        return stock_df
    
    def _load_indicator_data_from_db(self, db_manager):
        """
        從資料庫讀取指標資料
        
        參數:
        - db_manager: DatabaseManager 實例
        
        返回:
        - DataFrame: 指標資料
        """
        print("\n正在讀取指標數據...")
        
        # 讀取領先指標
        leading_df = db_manager.execute_query_dataframe(
            "SELECT * FROM leading_indicators_data ORDER BY date"
        )
        
        # 讀取同時指標
        coincident_df = db_manager.execute_query_dataframe(
            "SELECT * FROM coincident_indicators_data ORDER BY date"
        )
        
        # 讀取落後指標
        lagging_df = db_manager.execute_query_dataframe(
            "SELECT * FROM lagging_indicators_data ORDER BY date"
        )
        
        # 讀取綜合指標
        composite_df = db_manager.execute_query_dataframe(
            "SELECT * FROM composite_indicators_data ORDER BY date"
        )
        
        # 合併所有指標資料
        if leading_df.empty:
            indicator_df = pd.DataFrame()
        else:
            indicator_df = leading_df.copy()
            
            if not coincident_df.empty:
                indicator_df = indicator_df.merge(
                    coincident_df,
                    on='date',
                    how='outer',
                    suffixes=('', '_coincident')
                )
            
            if not lagging_df.empty:
                indicator_df = indicator_df.merge(
                    lagging_df,
                    on='date',
                    how='outer',
                    suffixes=('', '_lagging')
                )
            
            if not composite_df.empty:
                indicator_df = indicator_df.merge(
                    composite_df,
                    on='date',
                    how='outer',
                    suffixes=('', '_composite')
                )
            
            # 轉換日期格式
            indicator_df['indicator_date'] = pd.to_datetime(indicator_df['date'], format='%Y%m%d')
        
        # 建立欄位對應字典（資料庫欄位 -> CSV 欄位）
        rename_dict = {
            # 領先指標
            'export_order_index': 'leading_外銷訂單動向指數(以家數計)',
            'm1b_money_supply': 'leading_貨幣總計數M1B(百萬元)',
            'stock_price_index': 'leading_股價指數(Index1966=100)',
            'employment_net_entry_rate': 'leading_工業及服務業受僱員工淨進入率(%)',
            'building_floor_area': 'leading_建築物開工樓地板面積(住宅類住宅、商業辦公、工業倉儲)(千平方公尺)',
            'semiconductor_import': 'leading_名目半導體設備進口(新臺幣百萬元)',
            # 同時指標
            'industrial_production_index': 'coincident_工業生產指數(Index2021=100)',
            'electricity_consumption': 'coincident_電力(企業)總用電量(十億度)',
            'manufacturing_sales_index': 'coincident_製造業銷售量指數(Index2021=100)',
            'wholesale_retail_revenue': 'coincident_批發、零售及餐飲業營業額(十億元)',
            'overtime_hours': 'coincident_工業及服務業加班工時(小時)',
            'export_value': 'coincident_海關出口值(十億元)',
            'machinery_import': 'coincident_機械及電機設備進口值(十億元)',
            # 落後指標
            'unemployment_rate': 'lagging_失業率(%)',
            'labor_cost_index': 'lagging_製造業單位產出勞動成本指數(2021=100)',
            'loan_interest_rate': 'lagging_五大銀行新承做放款平均利率(年息百分比)',
            'financial_institution_loans': 'lagging_全體金融機構放款與投資(10億元)',
            'manufacturing_inventory': 'lagging_製造業存貨價值(千元)',
            # 綜合指標
            'leading_index': 'signal_領先指標綜合指數',
            'leading_index_no_trend': 'signal_領先指標不含趨勢指數',
            'coincident_index': 'signal_同時指標綜合指數',
            'coincident_index_no_trend': 'signal_同時指標不含趨勢指數',
            'lagging_index': 'signal_落後指標綜合指數',
            'lagging_index_no_trend': 'signal_落後指標不含趨勢指數',
            'business_cycle_score': 'signal_景氣對策信號綜合分數',
            'business_cycle_signal': 'signal_景氣對策信號'
        }
        
        # 只重新命名存在的欄位
        existing_rename_dict = {k: v for k, v in rename_dict.items() if k in indicator_df.columns}
        indicator_df = indicator_df.rename(columns=existing_rename_dict)
        
        print(f"  共讀取 {len(indicator_df)} 筆指標數據")
        
        return indicator_df
    
    def _align_indicators(self, stock_df, indicator_df):
        """
        對齊指標資料（n-2個月）
        
        參數:
        - stock_df: 股票價格資料 DataFrame
        - indicator_df: 指標資料 DataFrame
        
        返回:
        - DataFrame: 合併後的資料
        """
        print("\n正在對齊指標數據（n-2個月）...")
        
        result_rows = []
        indicator_cols = [col for col in indicator_df.columns 
                         if col not in ['date', 'indicator_date', 'created_at']]
        
        for idx, row in stock_df.iterrows():
            if idx % 1000 == 0:
                print(f"  處理進度：{idx}/{len(stock_df)} ({idx/len(stock_df)*100:.1f}%)")
            
            target_date = pd.Timestamp(row['date'])
            
            # 計算往前推2個月的日期（該月份的第一天）
            target_month = target_date.replace(day=1)
            indicator_month = target_month - pd.DateOffset(months=2)
            
            # 在指標數據中查找對應月份的數據
            # 指標資料是月度的，需要找到該月份的任何一天（通常會有多筆，取第一筆）
            mask = (indicator_df['indicator_date'].dt.year == indicator_month.year) & \
                   (indicator_df['indicator_date'].dt.month == indicator_month.month)
            
            matching_rows = indicator_df[mask]
            
            # 建立結果行
            result_row = {
                'date': row['date'],
                'ticker': row['ticker'],
                'close': row['close']
            }
            
            # 添加指標數據
            if len(matching_rows) > 0:
                indicator_row = matching_rows.iloc[0]
                for col in indicator_cols:
                    result_row[col] = indicator_row.get(col, None)
            else:
                # 如果找不到，設為 None
                for col in indicator_cols:
                    result_row[col] = None
            
            result_rows.append(result_row)
        
        # 轉換為 DataFrame
        result_df = pd.DataFrame(result_rows)
        
        # 確保欄位順序：date, ticker, close, 然後是指標欄位
        column_order = ['date', 'ticker', 'close'] + indicator_cols
        result_df = result_df[[col for col in column_order if col in result_df.columns]]
        
        return result_df
    
    def _normalize_ticker(self, ticker):
        """
        標準化 ticker 格式：6208 -> 006208, 2330 -> 2330
        
        參數:
        - ticker: ticker 值
        
        返回:
        - str: 標準化後的 ticker
        """
        if pd.isna(ticker):
            return None
        
        # 處理浮點數格式（如 6208.0 -> 6208）
        if isinstance(ticker, (int, float)):
            ticker = int(ticker)
        
        ticker_str = str(ticker)
        
        # 如果是 4 位數字，轉換為 6 位（6208 -> 006208）
        if len(ticker_str) == 4 and ticker_str.isdigit():
            return '00' + ticker_str
        
        return ticker_str
    
    def run_backtest(self, start_date, end_date, strategy_func, tickers=None):
        """
        執行回測
        
        參數:
        - start_date: 起始日期（'YYYY-MM-DD' 或 date 對象）
        - end_date: 結束日期（'YYYY-MM-DD' 或 date 對象）
        - strategy_func: 策略函數
        - tickers: 要回測的股票代號列表（預設所有）
        
        返回:
        - dict: 回測結果字典
        """
        # 轉換日期格式
        if isinstance(start_date, str):
            start_date = pd.Timestamp(start_date).date()
        if isinstance(end_date, str):
            end_date = pd.Timestamp(end_date).date()
        
        # 標準化 ticker 格式
        normalized_tickers = []
        if tickers:
            for t in tickers:
                normalized_t = self._normalize_ticker(t)
                if normalized_t:
                    normalized_tickers.append(normalized_t)
        
        if not normalized_tickers:
            raise ValueError("必須指定至少一個標的代號")
        
        # 載入資料（從資料庫讀取）
        df = self.load_data(normalized_tickers, start_date, end_date)
        
        if df.empty:
            raise ValueError(f"在日期範圍 {start_date} 至 {end_date} 內沒有資料")
        
        # 過濾 ticker（確保只包含指定的標的）
        df = df[df['ticker'].isin(normalized_tickers)].copy()
        
        if df.empty:
            raise ValueError(f"找不到指定股票代號的資料：{normalized_tickers}")
        
        print(f"\n[Info] 開始回測：{start_date} 至 {end_date}")
        print(f"[Info] 資料筆數：{len(df)} 筆")
        print(f"[Info] 股票代號：{sorted(df['ticker'].unique())}")
        print(f"[Info] 初始資金：{self.initial_capital:,.0f} 元")
        
        # 初始化策略狀態
        strategy_state = {
            'state': False,  # 是否持有股票
            'hedge_state': False,  # 是否持有避險資產
            'score': None,
            'prev_score': None,  # 上一個分數（用於計算動能）
            'm1b_yoy_month': None,  # M1B 年增率（從 leading_貨幣總計數M1B 取得）
            'score_momentum': None,  # 景氣分數動能
        }
        
        # 重置狀態
        self.cash = self.initial_capital
        self.positions = {}
        self.portfolio_value = []
        self.returns = []
        self.trades = []
        self.dates = []
        self.daily_positions = []
        self.daily_cash = []
        self._missing_price_warnings = []
        
        # 分批執行追蹤機制
        # {ticker: {'action': 'buy'/'sell', 'total_percent': float, 'executed_percent': float, 
        #           'days_remaining': int, 'start_date': date, 'trade_step': dict, ...}}
        split_orders = {}
        
        # 取得唯一的日期列表（所有 ticker 的日期合併）
        unique_dates = sorted(df['date'].unique())
        
        # 每日迭代
        prev_score = None
        prev_month_key = None
        
        for date in unique_dates:
            # 取得當天的所有資料（可能包含多個 ticker）
            day_data = df[df['date'] == date].copy()
            
            if day_data.empty:
                continue
            
            # 建立價格字典
            price_dict = {}
            for _, row in day_data.iterrows():
                ticker = row['ticker']
                close = row['close']
                if pd.notna(close) and close > 0:
                    price_dict[ticker] = close
            
            if not price_dict:
                # 如果當天沒有任何有效價格，跳過
                continue
            
            # 取得第一個 ticker 的指標數據（假設同一天所有 ticker 的指標相同）
            first_row = day_data.iloc[0]
            
            # 轉換 row 為字典以便策略使用
            row_dict = first_row.to_dict()
            
            # 更新策略狀態（從 row_dict 取得指標數據）
            score = row_dict.get('signal_景氣對策信號綜合分數')
            if pd.notna(score):
                strategy_state['score'] = float(score)
            else:
                strategy_state['score'] = None
            
            # 計算分數動能（跨月時計算）
            current_month_key = (date.year, date.month)
            if prev_month_key is not None and current_month_key != prev_month_key:
                # 跨月了，計算動能
                if prev_score is not None and strategy_state['score'] is not None:
                    strategy_state['score_momentum'] = strategy_state['score'] - prev_score
                else:
                    strategy_state['score_momentum'] = None
            elif prev_month_key is None:
                # 第一次，初始化
                strategy_state['score_momentum'] = None
            
            # 更新 M1B 相關數據（從 leading_貨幣總計數M1B 取得）
            m1b_value = row_dict.get('leading_貨幣總計數M1B(百萬元)')
            if pd.notna(m1b_value):
                strategy_state['m1b_yoy_month'] = float(m1b_value)
            else:
                strategy_state['m1b_yoy_month'] = None
            
            # 保存上一個分數和月份
            if strategy_state['score'] is not None:
                prev_score = strategy_state['score']
            prev_month_key = current_month_key
            
            # 計算投資組合價值（執行策略前）
            portfolio_value_before = self._calculate_portfolio_value(price_dict)
            
            # 1. 先處理待執行的分批訂單（如果有的話）
            orders_to_execute = []
            processed_tickers = set()  # 避免重複處理
            
            for ticker, split_order in list(split_orders.items()):
                # 檢查是否還有剩餘天數
                if split_order['days_remaining'] < 0:
                    # 如果已經沒有剩餘天數，移除追蹤
                    del split_orders[ticker]
                    continue
                
                # 如果 ticker 不在 price_dict 中（非交易日或無價格資料），跳過執行但減少剩餘天數
                if ticker not in price_dict:
                    # 減少剩餘天數，但不執行訂單
                    split_order['days_remaining'] -= 1
                    # 如果已經沒有剩餘天數，移除追蹤
                    if split_order['days_remaining'] < 0:
                        del split_orders[ticker]
                    continue
                
                # 如果已經處理過該 ticker，跳過
                if ticker in processed_tickers:
                    continue
                
                # 第6天（days_remaining == 0）：檢查剩餘現金是否足夠買一張
                if split_order['days_remaining'] == 0:
                    # 第6天：檢查剩餘現金並買進
                    if split_order['action'] == 'buy':
                        # 檢查剩餘現金是否足夠買一張
                        if ticker in price_dict:
                            price = price_dict[ticker]
                            min_shares = 1000
                            min_cost = min_shares * price + self.calculate_commission(min_shares * price)
                            
                            if self.cash >= min_cost:
                                # 使用所有可用現金買進
                                available_after_commission = self.cash / (1 + self.commission_rate)
                                shares_float = available_after_commission / price
                                shares = int(math.floor(shares_float / 1000)) * 1000
                                
                                if shares >= min_shares:
                                    # 執行買進
                                    today_order = {
                                        'action': 'buy',
                                        'ticker': ticker,
                                        'percent': 1.0,  # 使用所有可用現金
                                        'trade_step': split_order.get('trade_step'),
                                        'is_split_order': True,
                                        'is_last_split_day': True,  # 標記為最後一天
                                        'signal_score': split_order.get('signal_score'),
                                        'signal_text': split_order.get('signal_text'),
                                        'initial_portfolio_value': None,  # 第6天不使用初始價值
                                        'is_day6_check': True  # 標記為第6天檢查
                                    }
                                    orders_to_execute.append(today_order)
                                    processed_tickers.add(ticker)
                    
                    # 如果是賣出且需要觸發避險資產買進，第6天也要檢查
                    elif split_order['action'] == 'sell' and split_order.get('trigger_hedge_buy', False):
                        hedge_ticker = split_order.get('hedge_ticker')
                        if hedge_ticker and hedge_ticker in price_dict:
                            hedge_price = price_dict[hedge_ticker]
                            min_hedge_shares = 1000
                            min_hedge_cost = min_hedge_shares * hedge_price + self.calculate_commission(min_hedge_shares * hedge_price)
                            
                            if self.cash >= min_hedge_cost:
                                # 第6天：使用所有可用現金買進避險資產
                                available_after_commission = self.cash / (1 + self.commission_rate)
                                hedge_shares_float = available_after_commission / hedge_price
                                hedge_shares = int(math.floor(hedge_shares_float / 1000)) * 1000
                                
                                if hedge_shares >= min_hedge_shares:
                                    # 執行避險資產買進（使用特殊標記，讓 _execute_order 知道這是第6天檢查）
                                    hedge_order = {
                                        'action': 'buy',
                                        'ticker': hedge_ticker,
                                        'percent': 1.0,
                                        'trade_step': split_order.get('hedge_trade_step'),
                                        'is_split_order': True,
                                        'is_last_split_day': True,
                                        'signal_score': split_order.get('signal_score'),
                                        'signal_text': split_order.get('signal_text'),
                                        'is_day6_check': True,  # 標記為第6天檢查
                                        'is_hedge_buy': True  # 標記為避險資產買進
                                    }
                                    orders_to_execute.append(hedge_order)
                                    processed_tickers.add(hedge_ticker)
                    
                    # 移除追蹤（無論是否執行）
                    del split_orders[ticker]
                    continue
                
                # 計算今天要執行的比例（前5天）
                if split_order['days_remaining'] == 1:
                    # 第5天：執行剩餘的所有比例
                    today_percent = split_order['total_percent'] - split_order['executed_percent']
                else:
                    # 前4天：平均分配（每天 20%）
                    today_percent = split_order['total_percent'] / 5
                
                # 建立今天要執行的訂單
                is_last_day = (split_order['days_remaining'] == 1)
                today_order = {
                    'action': split_order['action'],
                    'ticker': ticker,
                    'percent': today_percent,
                    'trade_step': split_order.get('trade_step'),
                    'is_split_order': True,
                    'is_last_split_day': is_last_day,  # 標記是否為最後一天
                    'signal_score': split_order.get('signal_score'),
                    'signal_text': split_order.get('signal_text'),
                    # 傳遞初始持倉數量（用於賣出時計算固定數量）
                    'initial_shares': split_order.get('initial_shares'),
                    # 傳遞初始投資組合價值（用於買進時計算固定金額）
                    'initial_portfolio_value': split_order.get('initial_portfolio_value')
                }
                
                # 如果是賣出且需要觸發避險資產買進
                if split_order['action'] == 'sell' and split_order.get('trigger_hedge_buy', False):
                    hedge_ticker = split_order.get('hedge_ticker')
                    if hedge_ticker:
                        # 標記需要在賣出時同步買進避險資產（使用賣出得到的現金）
                        today_order['trigger_hedge_buy'] = True
                        today_order['hedge_ticker'] = hedge_ticker
                        today_order['hedge_trade_step'] = split_order.get('hedge_trade_step')
                
                orders_to_execute.append(today_order)
                processed_tickers.add(ticker)
                
                # 更新進度
                split_order['executed_percent'] += today_percent
                split_order['days_remaining'] -= 1
                
                # 如果已完成（days_remaining < 0），移除追蹤
                # 注意：days_remaining == 0 時保留，用於第6天檢查剩餘現金
                if split_order['days_remaining'] < 0:
                    del split_orders[ticker]
            
            # 2. 執行策略，取得新訂單
            orders = strategy_func(strategy_state, date, row_dict, price_dict, self.positions, portfolio_value_before)
            
            # 3. 處理策略產生的新訂單
            for order in orders:
                if order.get('split_execution', False):
                    # 標記為需要分批執行，加入追蹤
                    ticker = order['ticker']
                    
                    # 如果是賣出且需要觸發避險資產買進
                    hedge_ticker = None
                    if order.get('trigger_hedge_buy', False):
                        hedge_ticker = order.get('hedge_ticker')
                    
                    # 記錄初始持倉數量（用於賣出時計算固定數量）
                    # 記錄初始投資組合價值（用於買進時計算固定金額）
                    initial_shares = None
                    initial_portfolio_value = None
                    if order['action'] == 'sell':
                        initial_shares = self.positions.get(ticker, 0)
                    elif order['action'] == 'buy':
                        initial_portfolio_value = self._calculate_portfolio_value(price_dict)
                    
                    split_orders[ticker] = {
                        'action': order['action'],
                        'total_percent': order['percent'],
                        'executed_percent': 0.0,
                        'days_remaining': 6,  # 5天正常執行 + 1天檢查剩餘現金
                        'start_date': date,
                        'trade_step': order.get('trade_step'),
                        'signal_score': order.get('signal_score'),
                        'signal_text': order.get('signal_text'),
                        # 如果是賣出且需要觸發避險資產買進
                        'trigger_hedge_buy': order.get('trigger_hedge_buy', False),
                        'hedge_ticker': hedge_ticker,
                        'hedge_trade_step': order.get('hedge_trade_step'),
                        # 記錄初始持倉數量（用於賣出時計算固定數量）
                        'initial_shares': initial_shares,
                        # 記錄初始投資組合價值（用於買進時計算固定金額）
                        'initial_portfolio_value': initial_portfolio_value
                    }
                    
                    # 注意：分批訂單會在後續的交易日中執行，今天不執行
                    # 避險資產會在每次賣出時同步買進（使用賣出得到的現金）
                else:
                    # 立即執行
                    orders_to_execute.append(order)
            
            # 4. 執行所有訂單（包括分批訂單的當天部分和立即執行的訂單）
            for order in orders_to_execute:
                self._execute_order(order, date, price_dict)
            
            # 計算投資組合價值（執行策略後）
            portfolio_value = self._calculate_portfolio_value(price_dict)
            
            # 記錄日期、價值和持倉
            self.dates.append(date)
            self.portfolio_value.append(portfolio_value)
            self.daily_positions.append(dict(self.positions))  # 記錄當日持倉快照
            self.daily_cash.append(self.cash)  # 記錄當日現金餘額
            
            # 計算報酬率
            if len(self.portfolio_value) == 1:
                self.returns.append(0.0)
            else:
                prev_value = self.portfolio_value[-2]
                daily_return = (portfolio_value - prev_value) / prev_value if prev_value > 0 else 0.0
                self.returns.append(daily_return)
        
        # 計算績效指標
        metrics = self._calculate_metrics()
        
        # 輸出缺失價格警告摘要
        if self._missing_price_warnings:
            missing_by_ticker = {}
            for warning in self._missing_price_warnings:
                ticker = warning['ticker']
                if ticker not in missing_by_ticker:
                    missing_by_ticker[ticker] = []
                missing_by_ticker[ticker].append(warning)
            
            print(f"\n[Warning] 共有 {len(self._missing_price_warnings)} 筆訂單因缺少價格資料而被跳過：")
            for ticker, warnings in missing_by_ticker.items():
                print(f"  {ticker}: {len(warnings)} 筆（首次發生日期：{warnings[0]['date'].strftime('%Y-%m-%d')}）")
        
        # 計算最終持倉資訊
        final_positions = {}
        if self.dates and price_dict:
            last_date = self.dates[-1]
            last_day_data = df[df['date'] == last_date]
            
            for ticker, shares in self.positions.items():
                ticker_data = last_day_data[last_day_data['ticker'] == ticker]
                if not ticker_data.empty:
                    price = ticker_data.iloc[0]['close']
                    if pd.notna(price) and price > 0:
                        final_positions[ticker] = {
                            'shares': shares,
                            'price': float(price),
                            'value': shares * float(price)
                        }
        
        return {
            'dates': self.dates,
            'portfolio_value': self.portfolio_value,
            'returns': self.returns,
            'trades': self.trades,
            'metrics': metrics,
            'final_value': self.portfolio_value[-1] if self.portfolio_value else self.initial_capital,
            'total_return': (self.portfolio_value[-1] - self.initial_capital) / self.initial_capital if self.portfolio_value else 0,
            'final_positions': final_positions,
            'final_cash': self.cash,
            'positions': self.positions,
            'daily_positions': self.daily_positions,  # 每日持倉記錄
            'daily_cash': self.daily_cash  # 每日現金餘額記錄
        }
    
    def _execute_order(self, order, date, price_dict):
        """
        執行訂單
        
        參數:
        - order: 訂單字典 {'action': 'buy'/'sell', 'ticker': str, 'percent': float, ...}
        - date: 交易日期
        - price_dict: 價格字典
        """
        action = order.get('action')
        ticker = order.get('ticker')
        
        if ticker not in price_dict:
            print(f"[Warning] {date.strftime('%Y-%m-%d')} {ticker} 無價格資料，跳過訂單")
            self._missing_price_warnings.append({
                'date': date,
                'ticker': ticker,
                'action': action
            })
            return
        
        price = price_dict[ticker]
        
        if action == 'buy':
            # 計算買進金額（根據 percent）
            percent = order.get('percent', 1.0)
            is_split_order = order.get('is_split_order', False)
            is_last_split_day = order.get('is_last_split_day', False)
            is_day6_check = order.get('is_day6_check', False)  # 第6天檢查剩餘現金
            initial_portfolio_value = order.get('initial_portfolio_value')  # 分批執行時的初始投資組合價值
            
            # 檢查可用現金是否足夠買至少一張（1000股）
            min_shares = 1000  # 最小買進單位：一張
            min_cost = min_shares * price + self.calculate_commission(min_shares * price)
            
            if self.cash < min_cost:
                # 現金不足買一張，保留現金作為預備金，不買進
                return
            
            # 第6天檢查：使用所有可用現金買進
            if is_day6_check:
                # 使用所有可用現金買進
                available_after_commission = self.cash / (1 + self.commission_rate)
                shares_float = available_after_commission / price
                shares = int(math.floor(shares_float / 1000)) * 1000  # 向下取整到千股
                # 確保至少買一張
                if shares < min_shares:
                    shares = 0  # 不足一張，不買進
                # 確保不會超過可用現金
                if shares > 0:
                    actual_cost = shares * price + self.calculate_commission(shares * price)
                    while actual_cost > self.cash and shares >= min_shares:
                        shares -= 1000
                        if shares < min_shares:
                            shares = 0  # 不足一張，不買進
                            break
                        actual_cost = shares * price + self.calculate_commission(shares * price)
            # 如果是分批執行的最後一天（第5天），使用所有可用現金買進，避免剩餘現金
            elif is_split_order and is_last_split_day:
                # 最後一天：使用所有可用現金買進，忽略 buy_value
                available_cash = self.cash / (1 + self.commission_rate)
                shares_float = available_cash / price
                shares = int(math.floor(shares_float / 1000)) * 1000  # 向下取整到千股
                # 確保至少買一張
                if shares < min_shares:
                    shares = 0  # 不足一張，不買進
                # 確保不會超過可用現金
                if shares > 0:
                    actual_cost = shares * price + self.calculate_commission(shares * price)
                    while actual_cost > self.cash and shares >= min_shares:
                        shares -= 1000
                        if shares < min_shares:
                            shares = 0  # 不足一張，不買進
                            break
                        actual_cost = shares * price + self.calculate_commission(shares * price)
            else:
                # 其他情況：按原邏輯計算（使用 buy_value）
                # 如果是分批執行，使用初始投資組合價值計算固定金額，確保每天買進金額一致
                if is_split_order and initial_portfolio_value is not None and initial_portfolio_value > 0:
                    buy_value = initial_portfolio_value * percent
                else:
                    # 非分批執行：使用當前投資組合價值計算
                    portfolio_value = self._calculate_portfolio_value(price_dict)
                    buy_value = portfolio_value * percent
                
                # 計算手續費
                commission = self.calculate_commission(buy_value)
                total_cost = buy_value + commission
                
                # 檢查現金是否足夠
                if self.cash < total_cost:
                    # 現金不足，使用全部現金（扣除手續費）
                    available_cash = max(0, self.cash - commission)
                    if available_cash <= 0:
                        return  # 連手續費都不夠
                    buy_value = available_cash
                    total_cost = buy_value + commission
                
                # 計算股數（向下取整）
                shares = int(buy_value / price / 1000) * 1000  # 以千股為單位
                # 確保至少買一張
                if shares < min_shares:
                    shares = 0  # 不足一張，不買進
                # 檢查是否超過可用現金
                if shares > 0:
                    actual_cost = shares * price + self.calculate_commission(shares * price)
                    if actual_cost > self.cash:
                        # 調整為可用現金能買的最大股數
                        available_cash = self.cash / (1 + self.commission_rate)
                        shares_float = available_cash / price
                        shares = int(math.floor(shares_float / 1000)) * 1000
                        # 確保至少買一張
                        if shares < min_shares:
                            shares = 0  # 不足一張，不買進
                        else:
                            actual_cost = shares * price + self.calculate_commission(shares * price)
                            while actual_cost > self.cash and shares >= min_shares:
                                shares -= 1000
                                if shares < min_shares:
                                    shares = 0  # 不足一張，不買進
                                    break
                                actual_cost = shares * price + self.calculate_commission(shares * price)
            
            if shares <= 0:
                return
            
            # 重新計算手續費（基於實際買進金額）
            actual_buy_amount = shares * price
            actual_commission = self.calculate_commission(actual_buy_amount)
            actual_cost = actual_buy_amount + actual_commission
            
            # 更新現金和持倉
            self.cash -= actual_cost
            self.positions[ticker] = self.positions.get(ticker, 0) + shares
            
            # 記錄交易
            trade_record = {
                '日期': date,
                '動作': '買進',
                '交易步驟': self._format_trade_step(order.get('trade_step'), is_hedge=order.get('is_hedge_buy', False)),
                '標的代號': ticker,
                '股數': shares,
                '價格': round(price, 2),
                '成本': round(actual_buy_amount, 2),
                '手續費': round(actual_commission, 2),
                '總成本': round(actual_cost, 2),
                '景氣燈號分數': order.get('signal_score'),
                '景氣燈號': order.get('signal_text'),
            }
            
            # 添加策略相關的指標（如果有）
            if 'signal_score' in order:
                trade_record['景氣燈號分數'] = order['signal_score']
            if 'signal_text' in order:
                trade_record['景氣燈號'] = order['signal_text']
            
            self.trades.append(trade_record)
        
        elif action == 'sell':
            # 檢查持倉
            current_shares = self.positions.get(ticker, 0)
            if current_shares <= 0:
                return
            
            # 計算賣出股數（根據 percent）
            percent = order.get('percent', 1.0)
            is_last_split_day = order.get('is_last_split_day', False)
            is_split_order = order.get('is_split_order', False)
            initial_shares = order.get('initial_shares')  # 分批執行時的初始持倉數量
            
            # 如果 percent >= 1.0 或是最後一批（標記為 is_last_split_day），賣出所有持倉
            # 這樣可以確保分批執行時最後一天能完全清倉
            if percent >= 1.0 or is_last_split_day:
                shares = current_shares  # 賣出所有持倉，確保完全清倉
            elif is_split_order and initial_shares is not None and initial_shares > 0:
                # 分批執行：使用初始持倉數量計算固定數量，確保每天賣出量一致
                # percent 已經是每天的百分比（例如 0.2 = 20%），所以直接計算
                # 使用向上取整，確保每天賣出量足夠，最後一天會賣出剩餘部分
                daily_shares_float = initial_shares * percent  # 每天應該賣出的股數
                shares = int(math.ceil(daily_shares_float / 1000)) * 1000  # 向上取整到千股
            else:
                # 非分批執行：使用當前持倉數量計算
                shares = int(current_shares * percent / 1000) * 1000  # 以千股為單位
            
            if shares <= 0:
                return
            
            # 計算收入
            revenue = shares * price
            tax = self.calculate_tax(revenue)
            net_revenue = revenue - tax
            
            # 更新現金和持倉
            self.cash += net_revenue
            self.positions[ticker] = current_shares - shares
            
            if self.positions[ticker] <= 0:
                del self.positions[ticker]
            
            # 記錄交易
            trade_record = {
                '日期': date,
                '動作': '賣出',
                '交易步驟': self._format_trade_step(order.get('trade_step')),
                '標的代號': ticker,
                '股數': shares,
                '價格': round(price, 2),
                '收入': round(revenue, 2),
                '證交稅': round(tax, 2),
                '淨收入': round(net_revenue, 2),
            }
            
            # 添加策略相關的指標（如果有）
            if 'signal_score' in order:
                trade_record['景氣燈號分數'] = order['signal_score']
            if 'signal_text' in order:
                trade_record['景氣燈號'] = order['signal_text']
            
            self.trades.append(trade_record)
            
            # 檢查是否需要觸發避險資產買進
            # 第五天流程：賣出原先資產 -> 計算持有現金能買的張數 -> 買進
            # 前四天：使用20%賣出得到的現金買進
            if order.get('trigger_hedge_buy', False):
                hedge_ticker = order.get('hedge_ticker')
                if hedge_ticker and hedge_ticker in price_dict:
                    hedge_price = price_dict[hedge_ticker]
                    is_last_split_day = order.get('is_last_split_day', False)
                    
                    # 檢查可用現金是否足夠買至少一張（1000股）
                    min_hedge_shares = 1000
                    min_hedge_cost = min_hedge_shares * hedge_price + self.calculate_commission(min_hedge_shares * hedge_price)
                    
                    if self.cash >= min_hedge_cost and hedge_price > 0:
                        if is_last_split_day:
                            # 第五天：使用所有可用現金買進（賣出後的所有現金）
                            # 計算能買的最大張數
                            available_after_commission = self.cash / (1 + self.commission_rate)
                            hedge_shares_float = available_after_commission / hedge_price
                            hedge_shares = int(math.floor(hedge_shares_float / 1000)) * 1000  # 向下取整到千股
                            
                            # 確保至少買一張
                            if hedge_shares < min_hedge_shares:
                                hedge_shares = 0  # 不足一張，不買進
                            
                            # 確保不會超過可用現金
                            if hedge_shares > 0:
                                hedge_cost = hedge_shares * hedge_price
                                hedge_commission = self.calculate_commission(hedge_cost)
                                hedge_total_cost = hedge_cost + hedge_commission
                                
                                # 如果超過可用現金，調整股數
                                while hedge_total_cost > self.cash and hedge_shares >= min_hedge_shares:
                                    hedge_shares -= 1000
                                    if hedge_shares < min_hedge_shares:
                                        hedge_shares = 0  # 不足一張，不買進
                                        break
                                    hedge_cost = hedge_shares * hedge_price
                                    hedge_commission = self.calculate_commission(hedge_cost)
                                    hedge_total_cost = hedge_cost + hedge_commission
                        else:
                            # 前四天：使用當天賣出得到的現金買進（net_revenue）
                            # 但也要考慮累積的現金，盡可能買進更多
                            available_cash = self.cash  # 使用所有可用現金（包括之前累積的）
                            hedge_shares_float = available_cash / hedge_price
                            hedge_shares = int(math.floor(hedge_shares_float / 1000)) * 1000  # 向下取整到千股
                            
                            # 確保至少買一張
                            if hedge_shares < min_hedge_shares:
                                hedge_shares = 0  # 不足一張，不買進
                            
                            # 確保不超過可用現金
                            if hedge_shares > 0:
                                hedge_cost = hedge_shares * hedge_price
                                hedge_commission = self.calculate_commission(hedge_cost)
                                hedge_total_cost = hedge_cost + hedge_commission
                                
                                if hedge_total_cost > available_cash:
                                    # 調整股數
                                    available_after_commission = available_cash / (1 + self.commission_rate)
                                    hedge_shares_float = available_after_commission / hedge_price
                                    hedge_shares = int(math.floor(hedge_shares_float / 1000)) * 1000
                                    if hedge_shares < min_hedge_shares:
                                        hedge_shares = 0  # 不足一張，不買進
                                    else:
                                        hedge_cost = hedge_shares * hedge_price
                                        hedge_commission = self.calculate_commission(hedge_cost)
                                        hedge_total_cost = hedge_cost + hedge_commission
                        
                        if hedge_shares > 0:
                            hedge_cost = hedge_shares * hedge_price
                            hedge_commission = self.calculate_commission(hedge_cost)
                            hedge_total_cost = hedge_cost + hedge_commission
                            
                            if hedge_total_cost <= self.cash:
                                # 執行買進
                                self.cash -= hedge_total_cost
                                
                                if hedge_ticker in self.positions:
                                    self.positions[hedge_ticker] += hedge_shares
                                else:
                                    self.positions[hedge_ticker] = hedge_shares
                                
                                # 記錄避險資產買進交易
                                hedge_trade_record = {
                                    '日期': date,
                                    '動作': '買進',
                                    '交易步驟': self._format_trade_step(order.get('hedge_trade_step'), is_hedge=True),
                                    '標的代號': hedge_ticker,
                                    '股數': hedge_shares,
                                    '價格': round(hedge_price, 2),
                                    '成本': round(hedge_cost, 2),
                                    '手續費': round(hedge_commission, 2),
                                    '總成本': round(hedge_total_cost, 2),
                                }
                                
                                if 'signal_score' in order:
                                    hedge_trade_record['景氣燈號分數'] = order['signal_score']
                                if 'signal_text' in order:
                                    hedge_trade_record['景氣燈號'] = order['signal_text']
                                
                                self.trades.append(hedge_trade_record)
                elif hedge_ticker and hedge_ticker not in price_dict:
                    print(f"[Warning] {date.strftime('%Y-%m-%d')} 避險資產 {hedge_ticker} 無價格資料，跳過買進")
    
    def _format_trade_step(self, trade_step, is_hedge=False):
        """
        格式化交易步驟字串
        
        參數:
        - trade_step: 交易步驟字典 {'reason': str, 'conditions': [{'name': str, 'value': float}, ...]}
        - is_hedge: 是否為避險資產交易
        
        返回:
        - 格式化的交易步驟字串
        """
        if not trade_step:
            if is_hedge:
                return '同步買進避險資產'
            return '未知原因'
        
        reason = trade_step.get('reason', '未知原因')
        conditions = trade_step.get('conditions', [])
        
        if not conditions:
            return reason
        
        # 格式化條件字串
        condition_strs = []
        for condition in conditions:
            name = condition.get('name', '')
            value = condition.get('value')
            
            if name and value is not None:
                # 格式化數值
                if isinstance(value, float):
                    value_str = f"{value:.2f}"
                elif isinstance(value, (int, str)):
                    value_str = str(value)
                else:
                    value_str = str(value)
                
                condition_strs.append(f"{name}: {value_str}")
        
        if condition_strs:
            return f"{reason} | {' | '.join(condition_strs)}"
        else:
            return reason
    
    def _calculate_positions_value(self, price_dict):
        """計算持倉價值"""
        total_value = 0.0
        for ticker, shares in self.positions.items():
            if ticker in price_dict:
                total_value += shares * price_dict[ticker]
        
        return total_value
    
    def _calculate_portfolio_value(self, price_dict):
        """計算投資組合總價值"""
        return self.cash + self._calculate_positions_value(price_dict)
    
    def _calculate_metrics(self):
        """計算績效指標"""
        if not self.returns or len(self.returns) == 0:
            return {
                'annualized_return': 0.0,
                'volatility': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'total_trades': 0
            }
        
        returns_array = np.array(self.returns)
        
        # 年化報酬率
        total_return = (self.portfolio_value[-1] - self.initial_capital) / self.initial_capital if self.portfolio_value else 0
        days = len(self.returns)
        annualized_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
        
        # 波動率（年化）
        volatility = np.std(returns_array) * np.sqrt(252)
        
        # Sharpe Ratio（假設無風險利率為 0）
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        # 最大回撤
        portfolio_values = np.array(self.portfolio_value)
        cummax = np.maximum.accumulate(portfolio_values)
        drawdowns = (portfolio_values - cummax) / cummax
        max_drawdown = abs(np.min(drawdowns)) if len(drawdowns) > 0 else 0
        
        # 交易次數
        total_trades = len(self.trades)
        
        return {
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_trades': total_trades
        }
    
    def generate_position_summary(self):
        """產生持倉變動摘要"""
        if not self.trades:
            return []
        
        summary = []
        for trade in self.trades:
            summary.append(trade.copy())
        
        return summary

