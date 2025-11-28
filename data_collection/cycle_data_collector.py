"""
景氣燈號資料讀取模組
從 CSV 檔案讀取景氣指標資料，將月資料轉換為交易日資料
"""

import pandas as pd
import pandas_market_calendars as pmc
from datetime import datetime, timedelta
import os


class CycleDataCollector:
    """景氣燈號資料讀取器"""
    
    def __init__(self, csv_path='business_cycle/景氣指標與燈號.csv'):
        """
        初始化景氣燈號資料讀取器
        
        參數:
        - csv_path: CSV 檔案路徑
        """
        self.csv_path = csv_path
        self.monthly_data = None
        self.daily_data = None
    
    def load_cycle_data_from_csv(self):
        """
        從 CSV 讀取景氣指標資料
        
        回傳:
        - DataFrame 包含月資料
        """
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"找不到景氣指標 CSV 檔案: {self.csv_path}")
        
        print(f"[Info] 讀取景氣指標資料: {self.csv_path}")
        
        # 讀取 CSV，指定欄位名稱
        df = pd.read_csv(
            self.csv_path,
            encoding='utf-8',
            dtype={'Date': str}
        )
        
        # 重新命名欄位為英文（方便處理）
        df.columns = df.columns.str.strip()
        
        # 提取需要的欄位
        required_columns = {
            'Date': 'Date',
            '景氣對策信號綜合分數': 'score',
            '景氣對策信號': 'signal'
        }
        
        # 檢查必要欄位是否存在
        available_columns = {}
        for old_name, new_name in required_columns.items():
            if old_name in df.columns:
                available_columns[new_name] = df[old_name]
            else:
                print(f"[Warning] 找不到欄位: {old_name}")
        
        if 'Date' not in df.columns or '景氣對策信號綜合分數' not in df.columns:
            raise ValueError("CSV 檔案缺少必要欄位")
        
        # 建立新的 DataFrame
        result_df = pd.DataFrame({
            'date': df['Date'],
            'score': pd.to_numeric(df['景氣對策信號綜合分數'], errors='coerce'),
            'signal': df['景氣對策信號'].str.strip() if '景氣對策信號' in df.columns else None
        })
        
        # 移除 score 為 NaN 或 '-' 的資料
        result_df = result_df[result_df['score'].notna()]
        result_df = result_df[result_df['score'] != '-']
        
        # 將 date 從 YYYYMM 格式轉換為日期
        result_df['date'] = pd.to_datetime(result_df['date'], format='%Y%m', errors='coerce')
        result_df = result_df[result_df['date'].notna()]
        
        result_df = result_df.sort_values('date').reset_index(drop=True)
        
        self.monthly_data = result_df
        print(f"[Info] 成功讀取 {len(result_df)} 筆月資料")
        
        return result_df
    
    def convert_monthly_to_daily(self, start_date=None, end_date=None):
        """
        將月資料轉換為交易日資料
        
        參數:
        - start_date: 起始日期（datetime 或字串 'YYYY-MM-DD'），預設為資料的起始日期
        - end_date: 結束日期（datetime 或字串 'YYYY-MM-DD'），預設為資料的結束日期
        
        回傳:
        - DataFrame 包含交易日資料
        """
        if self.monthly_data is None:
            raise ValueError("請先呼叫 load_cycle_data_from_csv() 讀取資料")
        
        # 取得台灣交易日曆
        cal = pmc.get_calendar('XTAI')
        
        # 確定日期範圍
        if start_date is None:
            start_date = self.monthly_data['date'].min()
        else:
            if isinstance(start_date, str):
                start_date = pd.Timestamp(start_date)
        
        if end_date is None:
            end_date = datetime.now()
        else:
            if isinstance(end_date, str):
                end_date = pd.Timestamp(end_date)
        
        # 取得交易日列表
        trading_days = cal.valid_days(start_date=start_date, end_date=end_date)
        trading_days = [pd.Timestamp(day).normalize() for day in trading_days]
        
        print(f"[Info] 取得 {len(trading_days)} 個交易日（{start_date.date()} 至 {end_date.date()}）")
        
        # 建立每日資料 DataFrame
        daily_records = []
        
        for trading_day in trading_days:
            # 找到該交易日所屬的月份資料
            # 使用該月份的第一天作為關鍵字
            month_start = pd.Timestamp(trading_day.year, trading_day.month, 1)
            
            # 找到該月份的資料
            month_data = self.monthly_data[
                (self.monthly_data['date'].dt.year == trading_day.year) &
                (self.monthly_data['date'].dt.month == trading_day.month)
            ]
            
            if not month_data.empty:
                # 使用該月份的第一筆資料（通常只有一筆）
                month_row = month_data.iloc[0]
                daily_records.append({
                    'date': trading_day,
                    'score': month_row['score'],
                    'signal': month_row.get('signal', None)
                })
            else:
                # 如果找不到該月份的資料，嘗試使用前一個月的資料
                prev_month = month_start - pd.Timedelta(days=1)
                prev_month_data = self.monthly_data[
                    (self.monthly_data['date'].dt.year == prev_month.year) &
                    (self.monthly_data['date'].dt.month == prev_month.month)
                ]
                
                if not prev_month_data.empty:
                    prev_month_row = prev_month_data.iloc[0]
                    daily_records.append({
                        'date': trading_day,
                        'score': prev_month_row['score'],
                        'signal': prev_month_row.get('signal', None)
                    })
        
        daily_df = pd.DataFrame(daily_records)
        
        if daily_df.empty:
            print("[Warning] 轉換後的日資料為空")
            return pd.DataFrame()
        
        # 排序並計算 val_shifted（前一日數值）
        daily_df = daily_df.sort_values('date').reset_index(drop=True)
        daily_df['val_shifted'] = daily_df['score'].shift(1)
        
        # 格式化日期
        daily_df['date_str'] = daily_df['date'].dt.strftime('%Y-%m-%d')
        
        self.daily_data = daily_df
        print(f"[Info] 成功轉換為 {len(daily_df)} 筆交易日資料")
        
        return daily_df
    
    def process_cycle_data(self, start_date=None, end_date=None):
        """
        完整處理流程：讀取 CSV 並轉換為交易日資料
        
        參數:
        - start_date: 起始日期（datetime 或字串 'YYYY-MM-DD'）
        - end_date: 結束日期（datetime 或字串 'YYYY-MM-DD'）
        
        回傳:
        - DataFrame 包含處理後的交易日資料
        """
        # 讀取 CSV
        self.load_cycle_data_from_csv()
        
        # 轉換為交易日資料
        daily_df = self.convert_monthly_to_daily(start_date, end_date)
        
        return daily_df
    
    def get_cycle_score_by_date(self, date):
        """
        取得特定日期的景氣燈號分數
        
        參數:
        - date: 日期（datetime 或字串 'YYYY-MM-DD'）
        
        回傳:
        - 景氣燈號分數（如果找不到則回傳 None）
        """
        if self.daily_data is None:
            raise ValueError("請先呼叫 process_cycle_data() 處理資料")
        
        if isinstance(date, str):
            date = pd.Timestamp(date)
        
        # 找到最接近的交易日資料
        date_str = date.strftime('%Y-%m-%d')
        
        # 精確匹配
        match = self.daily_data[self.daily_data['date_str'] == date_str]
        
        if not match.empty:
            return match.iloc[0]['score']
        
        # 如果找不到，找最近的前一個交易日
        before = self.daily_data[self.daily_data['date'] <= date]
        if not before.empty:
            return before.iloc[-1]['score']
        
        return None
    
    def get_cycle_data_by_date_range(self, start_date, end_date):
        """
        取得日期範圍內的景氣燈號資料
        
        參數:
        - start_date: 起始日期（datetime 或字串 'YYYY-MM-DD'）
        - end_date: 結束日期（datetime 或字串 'YYYY-MM-DD'）
        
        回傳:
        - DataFrame
        """
        if self.daily_data is None:
            raise ValueError("請先呼叫 process_cycle_data() 處理資料")
        
        if isinstance(start_date, str):
            start_date = pd.Timestamp(start_date)
        if isinstance(end_date, str):
            end_date = pd.Timestamp(end_date)
        
        mask = (self.daily_data['date'] >= start_date) & (self.daily_data['date'] <= end_date)
        return self.daily_data[mask].copy()
    
    def save_cycle_data_to_db(self, db_manager, table_name='business_cycle_data'):
        """
        將處理後的資料儲存到資料庫
        
        參數:
        - db_manager: DatabaseManager 實例
        - table_name: 資料表名稱
        """
        if self.daily_data is None:
            raise ValueError("請先呼叫 process_cycle_data() 處理資料")
        
        # 準備儲存的資料
        df_to_save = self.daily_data[['date_str', 'score', 'val_shifted', 'signal']].copy()
        df_to_save.columns = ['date', 'score', 'val_shifted', 'signal']
        
        # 儲存到資料庫
        db_manager.save_dataframe(df_to_save, table_name, if_exists='replace')
        print(f"[Info] 景氣燈號資料已儲存到資料庫表: {table_name}")

