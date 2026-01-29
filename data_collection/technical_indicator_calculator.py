"""
技術指標計算模組
從 export_for_prediction.py 提取技術指標計算邏輯，支援日線和月線計算
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, List, Sequence
from data_collection.database_manager import DatabaseManager


def _first_valid(s: pd.Series):
    """取得第一個有效值"""
    s2 = s.dropna()
    return s2.iloc[0] if len(s2) else np.nan


def _last_valid(s: pd.Series):
    """取得最後一個有效值"""
    s2 = s.dropna()
    return s2.iloc[-1] if len(s2) else np.nan


class TechnicalIndicatorCalculator:
    """技術指標計算器"""
    
    def __init__(self, db_path='D:\\all_data\\taiwan_stock_all_data.db'):
        """
        初始化計算器
        
        參數:
        - db_path: 資料庫路徑
        """
        self.db_manager = DatabaseManager(db_path)
    
    def calculate_indicators_daily(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算日線技術指標
        
        參數:
        - df: 包含 date, ticker, open, high, low, close, volume 的 DataFrame
        
        回傳:
        - 包含技術指標的 DataFrame
        """
        df = df.copy()
        
        # 確保按日期排序
        df = df.sort_values('date').reset_index(drop=True)
        
        # 1. 移動平均線（MA5, MA20, MA60）
        df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
        df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
        df['ma60'] = df['close'].rolling(window=60, min_periods=1).mean()
        
        # 2. 股價相對於移動平均線的位置
        df['price_vs_ma5'] = (df['close'] - df['ma5']) / df['ma5'] * 100
        df['price_vs_ma20'] = (df['close'] - df['ma20']) / df['ma20'] * 100
        
        # 3. 波動率（過去20天的標準差）
        df['volatility_20'] = df['close'].rolling(window=20, min_periods=1).std()
        df['volatility_pct_20'] = (df['volatility_20'] / df['close']) * 100
        
        # 4. 過去N天的報酬率
        df['return_1d'] = df['close'].pct_change(1) * 100  # 1天報酬率
        df['return_5d'] = df['close'].pct_change(5) * 100  # 5天報酬率
        df['return_20d'] = df['close'].pct_change(20) * 100  # 20天報酬率
        
        # 5. RSI（相對強弱指標，14天）
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        # 避免除零錯誤
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)  # 當 loss 為 0 時，RSI 設為 50（中性）
        
        # 6. 成交量相關特徵
        if 'volume' in df.columns:
            df['volume_ma5'] = df['volume'].rolling(window=5, min_periods=1).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma5']
            # 處理無窮大值
            df['volume_ratio'] = df['volume_ratio'].replace([np.inf, -np.inf], np.nan)
        else:
            df['volume_ma5'] = np.nan
            df['volume_ratio'] = np.nan
        
        return df
    
    def aggregate_to_monthly(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        將日線資料彙總為月線
        
        參數:
        - df: 日線資料 DataFrame（包含 date, ticker, open, high, low, close, volume, turnover）
        
        回傳:
        - 月線資料 DataFrame
        """
        df = df.copy()
        
        # 確保 date 是 datetime 類型
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
        
        # 按 ticker 分組處理
        monthly_list = []
        for ticker, g in df.groupby('ticker'):
            g = g.sort_values('date').set_index('date')
            
            # 使用 resample('ME') 彙總為月線
            monthly = g.resample('ME').agg({
                'open': _first_valid,
                'high': 'max',
                'low': 'min',
                'close': _last_valid,
                'volume': 'sum',
                'turnover': 'sum'
            })
            
            # 移除沒有收盤價的月份
            monthly = monthly.dropna(subset=['close'])
            monthly = monthly.reset_index()
            monthly['ticker'] = ticker
            monthly_list.append(monthly)
        
        if not monthly_list:
            return pd.DataFrame()
        
        monthly_df = pd.concat(monthly_list, ignore_index=True)
        monthly_df = monthly_df.sort_values(['date', 'ticker']).reset_index(drop=True)
        
        return monthly_df
    
    def calculate_indicators_monthly(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算月線技術指標
        
        參數:
        - df: 月線資料 DataFrame（包含 date, ticker, close, volume）
        
        回傳:
        - 包含技術指標的 DataFrame
        """
        df = df.copy()
        
        # 確保按日期排序
        df = df.sort_values('date').reset_index(drop=True)
        
        # 1. 移動平均線（MA3, MA6, MA12）
        df['ma3'] = df['close'].rolling(window=3, min_periods=1).mean()
        df['ma6'] = df['close'].rolling(window=6, min_periods=1).mean()
        df['ma12'] = df['close'].rolling(window=12, min_periods=1).mean()
        
        # 2. 股價相對於移動平均線的位置
        df['price_vs_ma3'] = (df['close'] - df['ma3']) / df['ma3'] * 100
        df['price_vs_ma6'] = (df['close'] - df['ma6']) / df['ma6'] * 100
        
        # 3. 波動率（過去6個月的標準差）
        df['volatility_6'] = df['close'].rolling(window=6, min_periods=1).std()
        df['volatility_pct_6'] = (df['volatility_6'] / df['close']) * 100
        
        # 4. 過去N個月的報酬率
        df['return_1m'] = df['close'].pct_change(1) * 100  # 1個月報酬率
        df['return_3m'] = df['close'].pct_change(3) * 100  # 3個月報酬率
        df['return_12m'] = df['close'].pct_change(12) * 100  # 12個月報酬率
        
        # 5. RSI（相對強弱指標，6個月）
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=6, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=6, min_periods=1).mean()
        # 避免除零錯誤
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)  # 當 loss 為 0 時，RSI 設為 50（中性）
        
        # 6. 成交量相關特徵
        if 'volume' in df.columns:
            df['volume_ma3'] = df['volume'].rolling(window=3, min_periods=1).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma3']
            # 處理無窮大值
            df['volume_ratio'] = df['volume_ratio'].replace([np.inf, -np.inf], np.nan)
        else:
            df['volume_ma3'] = np.nan
            df['volume_ratio'] = np.nan
        
        return df
    
    def save_indicators_to_db(self, df: pd.DataFrame, table_name: str, if_exists='replace'):
        """
        將技術指標儲存到資料庫
        
        參數:
        - df: 包含技術指標的 DataFrame
        - table_name: 資料表名稱（'stock_technical_indicators' 或 'stock_technical_indicators_monthly'）
        - if_exists: 如果表存在時的處理方式（'replace', 'append', 'fail'）
        """
        if df.empty:
            print(f"[Warning] DataFrame 為空，跳過儲存到 {table_name}")
            return
        
        # 選擇要儲存的欄位
        if table_name == 'stock_technical_indicators':
            # 日線表欄位
            columns = [
                'date', 'ticker', 'ma5', 'ma20', 'ma60',
                'price_vs_ma5', 'price_vs_ma20',
                'volatility_20', 'volatility_pct_20',
                'return_1d', 'return_5d', 'return_20d',
                'rsi', 'volume_ma5', 'volume_ratio'
            ]
        elif table_name == 'stock_technical_indicators_monthly':
            # 月線表欄位
            columns = [
                'date', 'ticker', 'ma3', 'ma6', 'ma12',
                'price_vs_ma3', 'price_vs_ma6',
                'volatility_6', 'volatility_pct_6',
                'return_1m', 'return_3m', 'return_12m',
                'rsi', 'volume_ma3', 'volume_ratio'
            ]
        else:
            raise ValueError(f"未知的表名稱: {table_name}")
        
        # 確保 date 欄位是字串格式（YYYYMMDD）
        df_to_save = df[columns].copy()
        if pd.api.types.is_datetime64_any_dtype(df_to_save['date']):
            df_to_save['date'] = df_to_save['date'].dt.strftime('%Y%m%d')
        else:
            # 如果已經是字串，確保格式正確
            df_to_save['date'] = pd.to_datetime(df_to_save['date'], errors='coerce').dt.strftime('%Y%m%d')
        
        # 移除包含 NaN 的行（保留必要的欄位）
        df_to_save = df_to_save.dropna(subset=['date', 'ticker'])
        
        # 儲存到資料庫
        self.db_manager.save_dataframe(df_to_save, table_name, if_exists=if_exists)
    
    def calculate_and_save_daily(self, tickers: List[str], start_date: Optional[str] = None, 
                                 end_date: Optional[str] = None, if_exists='replace'):
        """
        計算並儲存日線技術指標
        
        參數:
        - tickers: 股票代號列表
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        - if_exists: 如果表存在時的處理方式
        """
        print(f"\n[Info] 開始計算日線技術指標...")
        print(f"股票代號: {tickers}")
        
        all_results = []
        for ticker in tickers:
            print(f"\n處理 {ticker}...")
            
            # 讀取股價資料
            stock_df = self.db_manager.get_stock_price(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date
            )
            
            if stock_df.empty:
                print(f"  [Warning] {ticker} 沒有資料，跳過")
                continue
            
            # 轉換日期格式
            stock_df['date'] = pd.to_datetime(stock_df['date'], format='%Y%m%d', errors='coerce')
            stock_df = stock_df.sort_values('date').reset_index(drop=True)
            
            # 計算技術指標
            indicators_df = self.calculate_indicators_daily(stock_df)
            all_results.append(indicators_df)
            
            print(f"  [Info] {ticker} 計算完成，共 {len(indicators_df)} 筆資料")
        
        if not all_results:
            print("[Error] 沒有計算出任何資料")
            return
        
        # 合併所有結果
        result_df = pd.concat(all_results, ignore_index=True)
        
        # 儲存到資料庫
        print(f"\n[Info] 儲存日線技術指標到資料庫...")
        self.save_indicators_to_db(result_df, 'stock_technical_indicators', if_exists=if_exists)
        print(f"[Info] 日線技術指標計算完成，共 {len(result_df)} 筆資料")
    
    def calculate_and_save_monthly(self, tickers: List[str], start_date: Optional[str] = None,
                                   end_date: Optional[str] = None, if_exists='replace'):
        """
        計算並儲存月線技術指標
        
        參數:
        - tickers: 股票代號列表
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        - if_exists: 如果表存在時的處理方式
        """
        print(f"\n[Info] 開始計算月線技術指標...")
        print(f"股票代號: {tickers}")
        
        all_results = []
        for ticker in tickers:
            print(f"\n處理 {ticker}...")
            
            # 讀取股價資料
            stock_df = self.db_manager.get_stock_price(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date
            )
            
            if stock_df.empty:
                print(f"  [Warning] {ticker} 沒有資料，跳過")
                continue
            
            # 轉換日期格式
            stock_df['date'] = pd.to_datetime(stock_df['date'], format='%Y%m%d', errors='coerce')
            stock_df = stock_df.sort_values('date').reset_index(drop=True)
            
            # 彙總為月線
            monthly_df = self.aggregate_to_monthly(stock_df)
            
            if monthly_df.empty:
                print(f"  [Warning] {ticker} 月線彙總結果為空，跳過")
                continue
            
            # 計算月線技術指標
            indicators_df = self.calculate_indicators_monthly(monthly_df)
            all_results.append(indicators_df)
            
            print(f"  [Info] {ticker} 計算完成，共 {len(indicators_df)} 筆資料")
        
        if not all_results:
            print("[Error] 沒有計算出任何資料")
            return
        
        # 合併所有結果
        result_df = pd.concat(all_results, ignore_index=True)
        
        # 儲存到資料庫
        print(f"\n[Info] 儲存月線技術指標到資料庫...")
        self.save_indicators_to_db(result_df, 'stock_technical_indicators_monthly', if_exists=if_exists)
        print(f"[Info] 月線技術指標計算完成，共 {len(result_df)} 筆資料")
    
    def calculate_and_save(self, tickers: List[str], calculate_daily: bool = True,
                          calculate_monthly: bool = True, start_date: Optional[str] = None,
                          end_date: Optional[str] = None, if_exists='replace'):
        """
        計算並儲存技術指標（支援同時計算日線和月線）
        
        參數:
        - tickers: 股票代號列表
        - calculate_daily: 是否計算日線
        - calculate_monthly: 是否計算月線
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        - if_exists: 如果表存在時的處理方式
        """
        if calculate_daily:
            self.calculate_and_save_daily(tickers, start_date, end_date, if_exists)
        
        if calculate_monthly:
            self.calculate_and_save_monthly(tickers, start_date, end_date, if_exists)
