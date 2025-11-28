"""
Orange 預測資料導出腳本
從資料庫讀取 006208 股價和景氣燈號資料，合併後計算特徵和目標變數，導出為 CSV
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collection.database_manager import DatabaseManager


class PredictionDataExporter:
    """預測資料導出器"""
    
    def __init__(self, db_path='D:\\all_data\\taiwan_stock_all_data.db', ticker='006208'):
        """
        初始化導出器
        
        參數:
        - db_path: 資料庫路徑
        - ticker: 股票代號（預設 006208，富邦台50）
        """
        self.db_manager = DatabaseManager(db_path)
        self.ticker = ticker
    
    def load_stock_data(self, start_date=None, end_date=None):
        """
        從資料庫載入股票資料
        
        參數:
        - start_date: 起始日期（YYYYMMDD 或 None）
        - end_date: 結束日期（YYYYMMDD 或 None）
        
        回傳:
        - DataFrame 包含日期和股價資訊
        """
        print(f"[Info] 載入 {self.ticker} 股價資料...")
        df = self.db_manager.get_stock_price(
            ticker=self.ticker,
            start_date=start_date,
            end_date=end_date
        )
        
        if df.empty:
            raise ValueError(f"找不到 {self.ticker} 的股價資料")
        
        # 確保日期格式正確
        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
        df = df.sort_values('date').reset_index(drop=True)
        
        print(f"[Info] 載入 {len(df)} 筆股價資料（{df['date'].min()} 至 {df['date'].max()}）")
        return df
    
    def load_cycle_data(self, start_date=None, end_date=None):
        """
        從資料庫載入景氣燈號資料
        
        參數:
        - start_date: 起始日期（YYYYMMDD 或 None）
        - end_date: 結束日期（YYYYMMDD 或 None）
        
        回傳:
        - DataFrame 包含日期和景氣燈號資訊
        """
        print(f"[Info] 載入景氣燈號資料...")
        
        query = "SELECT date, score, val_shifted, signal FROM business_cycle_data WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date"
        
        df = self.db_manager.execute_query_dataframe(query, params if params else None)
        
        if df.empty:
            raise ValueError("找不到景氣燈號資料")
        
        # 轉換日期格式
        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
        df = df.sort_values('date').reset_index(drop=True)
        
        print(f"[Info] 載入 {len(df)} 筆景氣燈號資料（{df['date'].min()} 至 {df['date'].max()}）")
        return df
    
    def encode_signal(self, signal):
        """
        將燈號編碼為數字
        
        參數:
        - signal: 燈號字串（藍燈、黃藍燈、綠燈、黃紅燈、紅燈）
        
        回傳:
        - 編碼後的數字
        """
        signal_map = {
            '藍燈': 1,
            '黃藍燈': 2,
            '綠燈': 3,
            '黃紅燈': 4,
            '紅燈': 5
        }
        return signal_map.get(signal, 3)  # 預設為綠燈（3）
    
    def create_features(self, merged_df):
        """
        建立特徵變數
        
        參數:
        - merged_df: 合併後的 DataFrame
        
        回傳:
        - 包含特徵的 DataFrame
        """
        df = merged_df.copy()
        
        # 1. 當月景氣對策信號綜合分數
        df['cycle_score'] = df['score']
        
        # 2. 燈號編碼
        df['signal_encoded'] = df['signal'].apply(self.encode_signal)
        
        # 3. 前1個月、前2個月、前3個月的分數（滯後特徵）
        # 注意：景氣燈號是月資料，所以這裡的「前N個月」需要用月來計算
        df['score_lag1'] = df['score'].shift(1)  # 前一天的分數
        df['score_lag2'] = df['score'].shift(2)
        df['score_lag3'] = df['score'].shift(3)
        
        # 4. 分數變化率
        df['score_change'] = df['score'] - df['score'].shift(1)
        df['score_change_pct'] = (df['score'] - df['score'].shift(1)) / df['score'].shift(1) * 100
        
        # 5. 技術指標：移動平均線（MA5, MA20）
        df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
        df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
        df['ma60'] = df['close'].rolling(window=60, min_periods=1).mean()
        
        # 6. 股價相對於移動平均線的位置
        df['price_vs_ma5'] = (df['close'] - df['ma5']) / df['ma5'] * 100
        df['price_vs_ma20'] = (df['close'] - df['ma20']) / df['ma20'] * 100
        
        # 7. 波動率（過去20天的標準差）
        df['volatility_20'] = df['close'].rolling(window=20, min_periods=1).std()
        df['volatility_pct_20'] = (df['volatility_20'] / df['close']) * 100
        
        # 8. 過去N天的報酬率
        df['return_1d'] = df['close'].pct_change(1) * 100  # 1天報酬率
        df['return_5d'] = df['close'].pct_change(5) * 100  # 5天報酬率
        df['return_20d'] = df['close'].pct_change(20) * 100  # 20天報酬率
        
        # 9. RSI（相對強弱指標，14天）
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 10. 成交量相關特徵
        if 'volume' in df.columns:
            df['volume_ma5'] = df['volume'].rolling(window=5, min_periods=1).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma5']
        
        return df
    
    def calculate_target(self, df, future_days=5):
        """
        計算目標變數：未來N天的報酬率（%）
        
        參數:
        - df: 包含股價的 DataFrame
        - future_days: 預測未來多少天的報酬率（預設 5 天）
        
        回傳:
        - 包含目標變數的 DataFrame
        """
        df = df.copy()
        
        # 計算未來N天的收盤價
        df['future_close'] = df['close'].shift(-future_days)
        
        # 計算未來報酬率（%）
        df[f'future_return_{future_days}d'] = ((df['future_close'] - df['close']) / df['close']) * 100
        
        # 計算未來漲跌方向（1=上漲，0=下跌）
        df[f'future_direction_{future_days}d'] = (df[f'future_return_{future_days}d'] > 0).astype(int)
        
        return df
    
    def merge_data(self, stock_df, cycle_df):
        """
        合併股票資料和景氣燈號資料
        
        參數:
        - stock_df: 股票資料 DataFrame
        - cycle_df: 景氣燈號資料 DataFrame
        
        回傳:
        - 合併後的 DataFrame
        """
        # 以日期為基準合併
        merged = pd.merge(
            stock_df[['date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 'turnover']],
            cycle_df[['date', 'score', 'val_shifted', 'signal']],
            on='date',
            how='inner'  # 只保留兩邊都有的日期
        )
        
        print(f"[Info] 合併後有 {len(merged)} 筆資料")
        return merged
    
    def export_to_csv(self, df, output_path='orange_data_export/prediction_data.csv'):
        """
        匯出資料為 CSV 檔案
        
        參數:
        - df: 要匯出的 DataFrame
        - output_path: 輸出檔案路徑
        """
        # 確保輸出目錄存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 選擇要匯出的欄位（排除未來價格等中間變數）
        export_columns = [
            'date',
            'ticker',
            'close',  # 當日收盤價
            'cycle_score',  # 當月景氣分數
            'signal_encoded',  # 燈號編碼
            'score_lag1', 'score_lag2', 'score_lag3',  # 滯後分數
            'score_change', 'score_change_pct',  # 分數變化
            'ma5', 'ma20', 'ma60',  # 移動平均線
            'price_vs_ma5', 'price_vs_ma20',  # 股價相對位置
            'volatility_20', 'volatility_pct_20',  # 波動率
            'return_1d', 'return_5d', 'return_20d',  # 過去報酬率
            'rsi',  # RSI指標
        ]
        
        # 如果有成交量，加入成交量特徵
        if 'volume_ratio' in df.columns:
            export_columns.extend(['volume', 'volume_ma5', 'volume_ratio'])
        
        # 加入目標變數
        target_columns = [col for col in df.columns if col.startswith('future_return_') or col.startswith('future_direction_')]
        export_columns.extend(target_columns)
        
        # 只保留存在的欄位
        export_columns = [col for col in export_columns if col in df.columns]
        
        export_df = df[export_columns].copy()
        
        # 移除包含 NaN 的目標變數行（最後幾天沒有未來資料）
        export_df = export_df.dropna(subset=target_columns)
        
        # 匯出為 CSV
        export_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"[Info] 資料已匯出到: {output_path}")
        print(f"[Info] 共匯出 {len(export_df)} 筆資料，{len(export_columns)} 個欄位")
        
        return export_df
    
    def export(self, start_date=None, end_date=None, future_days=5, output_path='orange_data_export/prediction_data.csv'):
        """
        執行完整匯出流程
        
        參數:
        - start_date: 起始日期（YYYYMMDD 或 None）
        - end_date: 結束日期（YYYYMMDD 或 None）
        - future_days: 預測未來多少天的報酬率（預設 5 天）
        - output_path: 輸出檔案路徑
        
        回傳:
        - 匯出的 DataFrame
        """
        print("=" * 60)
        print("Orange 預測資料導出")
        print("=" * 60)
        
        # 1. 載入股票資料
        stock_df = self.load_stock_data(start_date, end_date)
        
        # 2. 載入景氣燈號資料
        cycle_df = self.load_cycle_data(start_date, end_date)
        
        # 3. 合併資料
        merged_df = self.merge_data(stock_df, cycle_df)
        
        # 4. 建立特徵
        feature_df = self.create_features(merged_df)
        
        # 5. 計算目標變數
        target_df = self.calculate_target(feature_df, future_days=future_days)
        
        # 6. 匯出為 CSV
        export_df = self.export_to_csv(target_df, output_path)
        
        print("=" * 60)
        print("匯出完成！")
        print("=" * 60)
        
        return export_df


def main():
    """主程式"""
    import argparse
    
    parser = argparse.ArgumentParser(description='導出預測資料供 Orange 使用')
    parser.add_argument('--ticker', type=str, default='006208', help='股票代號（預設：006208）')
    parser.add_argument('--start-date', type=str, default=None, help='起始日期（YYYYMMDD）')
    parser.add_argument('--end-date', type=str, default=None, help='結束日期（YYYYMMDD）')
    parser.add_argument('--future-days', type=int, default=5, help='預測未來多少天的報酬率（預設：5）')
    parser.add_argument('--output', type=str, default='orange_data_export/prediction_data.csv', help='輸出檔案路徑')
    parser.add_argument('--db-path', type=str, default='D:\\all_data\\taiwan_stock_all_data.db', help='資料庫路徑')
    
    args = parser.parse_args()
    
    # 建立導出器
    exporter = PredictionDataExporter(db_path=args.db_path, ticker=args.ticker)
    
    # 執行匯出
    exporter.export(
        start_date=args.start_date,
        end_date=args.end_date,
        future_days=args.future_days,
        output_path=args.output
    )


if __name__ == '__main__':
    main()

