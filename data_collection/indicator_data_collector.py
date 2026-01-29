"""
景氣指標資料讀取模組
從 CSV 檔案讀取各種景氣指標資料，將月資料轉換為交易日資料
"""

import pandas as pd
import pandas_market_calendars as pmc
from datetime import datetime
import os


class IndicatorDataCollector:
    """景氣指標資料讀取器"""
    
    # CSV 檔案與資料表對應關係
    CSV_TABLE_MAPPING = {
        '領先指標構成項目.csv': {
            'table_name': 'leading_indicators_data',
            'date_column': 'Date',
            'column_mapping': {
                'Date': 'date',
                '外銷訂單動向指數(以家數計)': 'export_order_index',
                '貨幣總計數M1B(百萬元)': 'm1b_money_supply',
                '股價指數(Index1966=100)': 'stock_price_index',
                '工業及服務業受僱員工淨進入率(%)': 'employment_net_entry_rate',
                '建築物開工樓地板面積(住宅類住宅、商業辦公、工業倉儲)(千平方公尺)': 'building_floor_area',
                '名目半導體設備進口(新臺幣百萬元)': 'semiconductor_import'
            }
        },
        '同時指標構成項目.csv': {
            'table_name': 'coincident_indicators_data',
            'date_column': 'Date',
            'column_mapping': {
                'Date': 'date',
                '工業生產指數(Index2021=100)': 'industrial_production_index',
                '電力(企業)總用電量(十億度)': 'electricity_consumption',
                '製造業銷售量指數(Index2021=100)': 'manufacturing_sales_index',
                '批發、零售及餐飲業營業額(十億元)': 'wholesale_retail_revenue',
                '工業及服務業加班工時(小時)': 'overtime_hours',
                '海關出口值(十億元)': 'export_value',
                '機械及電機設備進口值(十億元)': 'machinery_import'
            }
        },
        '落後指標構成項目.csv': {
            'table_name': 'lagging_indicators_data',
            'date_column': 'Date',
            'column_mapping': {
                'Date': 'date',
                '失業率(%)': 'unemployment_rate',
                '製造業單位產出勞動成本指數(2021=100)': 'labor_cost_index',
                '五大銀行新承做放款平均利率(年息百分比)': 'loan_interest_rate',
                '全體金融機構放款與投資(10億元)': 'financial_institution_loans',
                '製造業存貨價值(千元)': 'manufacturing_inventory'
            }
        },
        '景氣指標與燈號.csv': {
            'table_name': 'composite_indicators_data',
            'date_column': 'Date',
            'column_mapping': {
                'Date': 'date',
                '領先指標綜合指數': 'leading_index',
                '領先指標不含趨勢指數': 'leading_index_no_trend',
                '同時指標綜合指數': 'coincident_index',
                '同時指標不含趨勢指數': 'coincident_index_no_trend',
                '落後指標綜合指數': 'lagging_index',
                '落後指標不含趨勢指數': 'lagging_index_no_trend',
                '景氣對策信號綜合分數': 'business_cycle_score',
                '景氣對策信號': 'business_cycle_signal'
            }
        },
        '景氣對策信號構成項目.csv': {
            'table_name': 'business_cycle_signal_components_data',
            'date_column': 'Date',
            'column_mapping': {
                'Date': 'date',
                '貨幣總計數M1B(百萬元)': 'm1b_money_supply',
                '股價指數(Index1966=100)': 'stock_price_index',
                '工業生產指數(Index2021=100)': 'industrial_production_index',
                '工業及服務業加班工時(小時)': 'overtime_hours',
                '海關出口值(十億元)': 'export_value',
                '機械及電機設備進口值(十億元)': 'machinery_import',
                '製造業銷售量指數(Index2021=100)': 'manufacturing_sales_index',
                '批發、零售及餐飲業營業額(十億元)': 'wholesale_retail_revenue'
            }
        }
    }
    
    def __init__(self, base_path='business_cycle'):
        """
        初始化景氣指標資料讀取器
        
        參數:
        - base_path: CSV 檔案所在資料夾路徑
        """
        self.base_path = base_path
    
    def load_csv_to_dataframe(self, csv_path):
        """
        讀取 CSV 檔案並轉換為 DataFrame
        
        參數:
        - csv_path: CSV 檔案路徑
        
        回傳:
        - DataFrame 包含月資料
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"找不到 CSV 檔案: {csv_path}")
        
        csv_name = os.path.basename(csv_path)
        if csv_name not in self.CSV_TABLE_MAPPING:
            raise ValueError(f"不支援的 CSV 檔案: {csv_name}")
        
        config = self.CSV_TABLE_MAPPING[csv_name]
        column_mapping = config['column_mapping']
        
        print(f"[Info] 讀取 CSV 檔案: {csv_path}")
        
        # 讀取 CSV
        df = pd.read_csv(
            csv_path,
            encoding='utf-8',
            dtype={config['date_column']: str}
        )
        
        # 清理欄位名稱（移除前後空白和引號）
        df.columns = df.columns.str.strip().str.strip('"')
        
        # 檢查必要欄位
        if config['date_column'] not in df.columns:
            raise ValueError(f"CSV 檔案缺少必要欄位: {config['date_column']}")
        
        # 建立新的 DataFrame，只包含需要的欄位
        result_data = {}
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                # 如果是日期欄位，保持原樣（稍後轉換）
                if old_col == config['date_column']:
                    result_data[new_col] = df[old_col]
                else:
                    # 嘗試轉換為數值，失敗則保持原樣
                    result_data[new_col] = pd.to_numeric(df[old_col], errors='coerce')
            else:
                print(f"[Warning] 找不到欄位: {old_col}，將設為 NULL")
                result_data[new_col] = None
        
        result_df = pd.DataFrame(result_data)
        
        # 將 date 從 YYYYMM 格式轉換為日期
        result_df['date'] = pd.to_datetime(result_df['date'], format='%Y%m', errors='coerce')
        result_df = result_df[result_df['date'].notna()]
        
        if result_df.empty:
            print(f"[Warning] CSV 檔案 {csv_name} 沒有有效的資料")
            return pd.DataFrame()
        
        result_df = result_df.sort_values('date').reset_index(drop=True)
        print(f"[Info] 成功讀取 {len(result_df)} 筆月資料")
        
        return result_df
    
    def convert_monthly_to_daily(self, monthly_df, start_date=None, end_date=None):
        """
        將月資料轉換為交易日資料
        
        參數:
        - monthly_df: 月資料 DataFrame
        - start_date: 起始日期（datetime 或字串 'YYYY-MM-DD'），預設為資料的起始日期
        - end_date: 結束日期（datetime 或字串 'YYYY-MM-DD'），預設為今天
        
        回傳:
        - DataFrame 包含交易日資料
        """
        if monthly_df.empty:
            return pd.DataFrame()
        
        # 取得台灣交易日曆
        cal = pmc.get_calendar('XTAI')
        
        # 確定日期範圍
        if start_date is None:
            start_date = monthly_df['date'].min()
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
            month_data = monthly_df[
                (monthly_df['date'].dt.year == trading_day.year) &
                (monthly_df['date'].dt.month == trading_day.month)
            ]
            
            if not month_data.empty:
                # 使用該月份的第一筆資料（通常只有一筆）
                month_row = month_data.iloc[0].to_dict()
                month_row['date'] = trading_day
                daily_records.append(month_row)
            else:
                # 如果找不到該月份的資料，嘗試使用前一個月的資料
                month_start = pd.Timestamp(trading_day.year, trading_day.month, 1)
                prev_month = month_start - pd.Timedelta(days=1)
                prev_month_data = monthly_df[
                    (monthly_df['date'].dt.year == prev_month.year) &
                    (monthly_df['date'].dt.month == prev_month.month)
                ]
                
                if not prev_month_data.empty:
                    prev_month_row = prev_month_data.iloc[0].to_dict()
                    prev_month_row['date'] = trading_day
                    daily_records.append(prev_month_row)
        
        daily_df = pd.DataFrame(daily_records)
        
        if daily_df.empty:
            print("[Warning] 轉換後的日資料為空")
            return pd.DataFrame()
        
        # 排序
        daily_df = daily_df.sort_values('date').reset_index(drop=True)
        
        # 格式化日期為 YYYYMMDD 字串
        daily_df['date_str'] = daily_df['date'].dt.strftime('%Y%m%d')
        
        print(f"[Info] 成功轉換為 {len(daily_df)} 筆交易日資料")
        
        return daily_df
    
    def import_single_indicator(self, csv_name, db_manager, start_date=None, end_date=None):
        """
        匯入單一 CSV 檔案
        
        參數:
        - csv_name: CSV 檔案名稱（例如：'領先指標構成項目.csv'）
        - db_manager: DatabaseManager 實例
        - start_date: 起始日期（可選）
        - end_date: 結束日期（可選）
        
        回傳:
        - dict 包含匯入結果
        """
        if csv_name not in self.CSV_TABLE_MAPPING:
            return {
                'success': False,
                'error': f'不支援的 CSV 檔案: {csv_name}'
            }
        
        config = self.CSV_TABLE_MAPPING[csv_name]
        table_name = config['table_name']
        csv_path = os.path.join(self.base_path, csv_name)
        
        try:
            # 讀取 CSV
            monthly_df = self.load_csv_to_dataframe(csv_path)
            if monthly_df.empty:
                return {
                    'success': False,
                    'error': 'CSV 檔案沒有有效資料'
                }
            
            # 轉換為交易日資料
            daily_df = self.convert_monthly_to_daily(monthly_df, start_date, end_date)
            if daily_df.empty:
                return {
                    'success': False,
                    'error': '轉換後的交易日資料為空'
                }
            
            # 準備儲存的資料（只保留需要的欄位，排除 date 和 date_str）
            columns_to_save = [col for col in daily_df.columns if col not in ['date', 'date_str']]
            df_to_save = daily_df[['date_str'] + columns_to_save].copy()
            df_to_save.columns = ['date'] + columns_to_save
            
            # 儲存到資料庫
            db_manager.save_dataframe(df_to_save, table_name, if_exists='replace')
            
            return {
                'success': True,
                'table_name': table_name,
                'records': len(df_to_save)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def import_all_indicators(self, db_manager, start_date=None, end_date=None):
        """
        一鍵匯入所有 5 個 CSV 檔案
        
        參數:
        - db_manager: DatabaseManager 實例
        - start_date: 起始日期（可選）
        - end_date: 結束日期（可選）
        
        回傳:
        - dict 包含所有匯入結果
        """
        results = {}
        
        for csv_name in self.CSV_TABLE_MAPPING.keys():
            print(f"\n{'='*60}")
            print(f"匯入: {csv_name}")
            print(f"{'='*60}")
            
            result = self.import_single_indicator(csv_name, db_manager, start_date, end_date)
            results[csv_name] = result
            
            if result['success']:
                print(f"[Success] {csv_name} 匯入成功，共 {result['records']} 筆資料")
            else:
                print(f"[Error] {csv_name} 匯入失敗: {result.get('error', '未知錯誤')}")
        
        return results
    
    def calculate_and_save_merged_indicators(self, db_manager):
        """
        計算並儲存合併後的總經指標到 merged_economic_indicators 表
        
        參數:
        - db_manager: DatabaseManager 實例
        
        邏輯:
        1. 從資料庫讀取各指標表（leading, coincident, lagging, composite）
        2. 添加前綴（leading_, coincident_, lagging_, signal_）
        3. 合併所有指標（inner join on date）
        4. 動態調整表結構（如果需要）
        5. 儲存到 merged_economic_indicators 表
        """
        print("\n[Info] 開始計算合併總經指標...")
        
        try:
            # 1. 從資料庫讀取各指標表
            leading_df = db_manager.execute_query_dataframe(
                "SELECT * FROM leading_indicators_data ORDER BY date"
            )
            coincident_df = db_manager.execute_query_dataframe(
                "SELECT * FROM coincident_indicators_data ORDER BY date"
            )
            lagging_df = db_manager.execute_query_dataframe(
                "SELECT * FROM lagging_indicators_data ORDER BY date"
            )
            composite_df = db_manager.execute_query_dataframe(
                "SELECT * FROM composite_indicators_data ORDER BY date"
            )
            
            # 檢查是否有足夠的資料
            if leading_df.empty and coincident_df.empty and lagging_df.empty and composite_df.empty:
                print("[Warning] 所有指標表都是空的，無法計算合併指標")
                return
            
            # 2. 添加前綴並準備合併
            merged_df = None
            
            # 處理領先指標
            if not leading_df.empty:
                leading_merged = leading_df.copy()
                # 將 date 轉換為 indicator_date（YYYYMMDD 格式）
                leading_merged['indicator_date'] = pd.to_datetime(leading_merged['date'], format='%Y%m%d', errors='coerce')
                if leading_merged['indicator_date'].isna().all():
                    # 如果 YYYYMMDD 格式失敗，嘗試 YYYY-MM-DD
                    leading_merged['indicator_date'] = pd.to_datetime(leading_merged['date'], errors='coerce')
                # 過濾掉 NaN 值
                leading_merged = leading_merged[leading_merged['indicator_date'].notna()]
                leading_merged['indicator_date'] = leading_merged['indicator_date'].dt.strftime('%Y%m%d')
                
                # 添加前綴（排除 date 和 created_at）
                cols_to_rename = {col: f'leading_{col}' for col in leading_merged.columns 
                                 if col not in ['date', 'indicator_date', 'created_at']}
                leading_merged = leading_merged.rename(columns=cols_to_rename)
                leading_merged = leading_merged[['indicator_date'] + [col for col in leading_merged.columns 
                                                                      if col.startswith('leading_')]]
                merged_df = leading_merged
            
            # 合併同時指標
            if not coincident_df.empty:
                coincident_merged = coincident_df.copy()
                coincident_merged['indicator_date'] = pd.to_datetime(coincident_merged['date'], format='%Y%m%d', errors='coerce')
                if coincident_merged['indicator_date'].isna().all():
                    coincident_merged['indicator_date'] = pd.to_datetime(coincident_merged['date'], errors='coerce')
                # 過濾掉 NaN 值
                coincident_merged = coincident_merged[coincident_merged['indicator_date'].notna()]
                coincident_merged['indicator_date'] = coincident_merged['indicator_date'].dt.strftime('%Y%m%d')
                
                cols_to_rename = {col: f'coincident_{col}' for col in coincident_merged.columns 
                                 if col not in ['date', 'indicator_date', 'created_at']}
                coincident_merged = coincident_merged.rename(columns=cols_to_rename)
                coincident_merged = coincident_merged[['indicator_date'] + [col for col in coincident_merged.columns 
                                                                           if col.startswith('coincident_')]]
                
                if merged_df is None:
                    merged_df = coincident_merged
                else:
                    merged_df = merged_df.merge(coincident_merged, on='indicator_date', how='inner')
            
            # 合併落後指標
            if not lagging_df.empty:
                lagging_merged = lagging_df.copy()
                lagging_merged['indicator_date'] = pd.to_datetime(lagging_merged['date'], format='%Y%m%d', errors='coerce')
                if lagging_merged['indicator_date'].isna().all():
                    lagging_merged['indicator_date'] = pd.to_datetime(lagging_merged['date'], errors='coerce')
                # 過濾掉 NaN 值
                lagging_merged = lagging_merged[lagging_merged['indicator_date'].notna()]
                lagging_merged['indicator_date'] = lagging_merged['indicator_date'].dt.strftime('%Y%m%d')
                
                cols_to_rename = {col: f'lagging_{col}' for col in lagging_merged.columns 
                                 if col not in ['date', 'indicator_date', 'created_at']}
                lagging_merged = lagging_merged.rename(columns=cols_to_rename)
                lagging_merged = lagging_merged[['indicator_date'] + [col for col in lagging_merged.columns 
                                                                      if col.startswith('lagging_')]]
                
                if merged_df is None:
                    merged_df = lagging_merged
                else:
                    merged_df = merged_df.merge(lagging_merged, on='indicator_date', how='inner')
            
            # 合併綜合指標（signal_前綴）
            if not composite_df.empty:
                signal_merged = composite_df.copy()
                signal_merged['indicator_date'] = pd.to_datetime(signal_merged['date'], format='%Y%m%d', errors='coerce')
                if signal_merged['indicator_date'].isna().all():
                    signal_merged['indicator_date'] = pd.to_datetime(signal_merged['date'], errors='coerce')
                # 過濾掉 NaN 值
                signal_merged = signal_merged[signal_merged['indicator_date'].notna()]
                signal_merged['indicator_date'] = signal_merged['indicator_date'].dt.strftime('%Y%m%d')
                
                cols_to_rename = {col: f'signal_{col}' for col in signal_merged.columns 
                                 if col not in ['date', 'indicator_date', 'created_at']}
                signal_merged = signal_merged.rename(columns=cols_to_rename)
                signal_merged = signal_merged[['indicator_date'] + [col for col in signal_merged.columns 
                                                                    if col.startswith('signal_')]]
                
                if merged_df is None:
                    merged_df = signal_merged
                else:
                    merged_df = merged_df.merge(signal_merged, on='indicator_date', how='inner')
            
            if merged_df is None or merged_df.empty:
                print("[Warning] 合併後的指標資料為空")
                return
            
            # 3. 動態調整表結構
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            try:
                # 檢查現有欄位
                cursor.execute("PRAGMA table_info(merged_economic_indicators)")
                existing_columns = [col[1] for col in cursor.fetchall()]
                
                # 為新欄位添加列
                for col in merged_df.columns:
                    if col not in existing_columns and col != 'indicator_date':
                        try:
                            cursor.execute(f"ALTER TABLE merged_economic_indicators ADD COLUMN {col} REAL")
                            print(f"[Info] 新增欄位: {col}")
                        except Exception as e:
                            print(f"[Warning] 無法新增欄位 {col}: {e}")
                
                conn.commit()
            finally:
                conn.close()
            
            # 4. 儲存到資料庫
            db_manager.save_dataframe(merged_df, 'merged_economic_indicators', if_exists='replace')
            print(f"[Success] 合併總經指標計算完成，共 {len(merged_df)} 筆資料")
            
        except Exception as e:
            print(f"[Error] 計算合併總經指標失敗: {e}")
            import traceback
            traceback.print_exc()
            raise

