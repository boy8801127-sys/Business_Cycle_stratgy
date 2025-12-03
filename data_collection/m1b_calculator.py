"""
M1B 年增率計算模組
計算貨幣總計數 M1B 的月對月年增率和年增率動能
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class M1BCalculator:
    """M1B 年增率計算器"""
    
    def __init__(self):
        """初始化計算器"""
        pass
    
    def calculate_yoy_month(self, df):
        """
        計算月對月年增率（當前月份 vs 去年同月份）
        
        參數:
        - df: DataFrame 包含 date 和 m1b_money_supply 欄位
        
        回傳:
        - DataFrame 新增 m1b_yoy_month 欄位
        """
        if df.empty or 'm1b_money_supply' not in df.columns:
            return df
        
        result_df = df.copy()
        
        # 保存原始日期格式（如果還沒有保存）
        if 'date_orig' not in result_df.columns:
            result_df['date_orig'] = result_df['date'].copy()
        
        # 確保日期格式正確（用於計算）
        if 'date' in result_df.columns:
            result_df['date_parsed'] = pd.to_datetime(result_df['date'], format='%Y%m%d', errors='coerce')
        else:
            result_df['date_parsed'] = pd.to_datetime(result_df['date_orig'], format='%Y%m%d', errors='coerce')
        
        # 新增年份和月份欄位
        result_df['year'] = result_df['date_parsed'].dt.year
        result_df['month'] = result_df['date_parsed'].dt.month
        
        # 按年份和月份分組，取得每個月的 M1B 值（同一月的所有交易日使用相同值）
        monthly_data = result_df.groupby(['year', 'month'])['m1b_money_supply'].first().reset_index()
        monthly_data.columns = ['year', 'month', 'm1b_value']
        
        # 計算年增率
        yoy_values = []
        
        for idx, row in result_df.iterrows():
            current_year = row['year']
            current_month = row['month']
            current_m1b = row['m1b_money_supply']
            
            if pd.isna(current_m1b):
                yoy_values.append(None)
                continue
            
            # 找去年同月的數據
            last_year_data = monthly_data[
                (monthly_data['year'] == current_year - 1) &
                (monthly_data['month'] == current_month)
            ]
            
            if not last_year_data.empty and not pd.isna(last_year_data.iloc[0]['m1b_value']):
                last_year_m1b = last_year_data.iloc[0]['m1b_value']
                if last_year_m1b != 0:
                    yoy = ((current_m1b - last_year_m1b) / last_year_m1b) * 100
                    yoy_values.append(yoy)
                else:
                    yoy_values.append(None)
            else:
                yoy_values.append(None)
        
        result_df['m1b_yoy_month'] = yoy_values
        
        # 移除臨時欄位（保留 date_orig 和原始 date）
        result_df = result_df.drop(columns=['year', 'month', 'date_parsed'], errors='ignore')
        
        return result_df
    
    def calculate_yoy_momentum(self, df):
        """
        計算年增率動能（當前年增率 - 上月年增率）
        
        參數:
        - df: DataFrame 包含 date、m1b_money_supply 和 m1b_yoy_month 欄位
        
        回傳:
        - DataFrame 新增 m1b_yoy_momentum 欄位
        """
        if df.empty or 'm1b_yoy_month' not in df.columns:
            return df
        
        result_df = df.copy()
        
        # 保存原始日期格式（如果還沒有保存）
        if 'date_orig' not in result_df.columns:
            result_df['date_orig'] = result_df['date'].copy()
        
        # 確保日期格式正確並排序（用於計算）
        if 'date_parsed' in result_df.columns:
            result_df['date_parsed'] = pd.to_datetime(result_df['date_parsed'], format='%Y%m%d', errors='coerce')
        else:
            if 'date' in result_df.columns:
                result_df['date_parsed'] = pd.to_datetime(result_df['date'], format='%Y%m%d', errors='coerce')
            else:
                result_df['date_parsed'] = pd.to_datetime(result_df['date_orig'], format='%Y%m%d', errors='coerce')
        
        result_df = result_df.sort_values('date_parsed').reset_index(drop=True)
        
        # 新增年份和月份欄位
        result_df['year'] = result_df['date_parsed'].dt.year
        result_df['month'] = result_df['date_parsed'].dt.month
        
        # 按年份和月份分組，取得每個月的年增率值（同一月的所有交易日使用相同值）
        monthly_yoy = result_df.groupby(['year', 'month'])['m1b_yoy_month'].first().reset_index()
        monthly_yoy.columns = ['year', 'month', 'yoy_value']
        
        # 計算年增率動能
        momentum_values = []
        
        for idx, row in result_df.iterrows():
            current_year = row['year']
            current_month = row['month']
            current_yoy = row['m1b_yoy_month']
            
            if pd.isna(current_yoy):
                momentum_values.append(None)
                continue
            
            # 計算上一個月的年份和月份
            if current_month == 1:
                prev_year = current_year - 1
                prev_month = 12
            else:
                prev_year = current_year
                prev_month = current_month - 1
            
            # 找上一個月的年增率
            prev_month_data = monthly_yoy[
                (monthly_yoy['year'] == prev_year) &
                (monthly_yoy['month'] == prev_month)
            ]
            
            if not prev_month_data.empty and not pd.isna(prev_month_data.iloc[0]['yoy_value']):
                prev_yoy = prev_month_data.iloc[0]['yoy_value']
                # 計算動能：當前年增率 - 上月年增率
                momentum = current_yoy - prev_yoy
                momentum_values.append(momentum)
            else:
                momentum_values.append(None)
        
        result_df['m1b_yoy_momentum'] = momentum_values
        
        # 移除臨時欄位（保留 date_orig 和原始 date）
        result_df = result_df.drop(columns=['year', 'month', 'date_parsed'], errors='ignore')
        
        return result_df
    
    def calculate_m1b_mom(self, df):
        """
        計算月對月變化率（當月 M1B vs 上月 M1B 的增減百分比）
        
        參數:
        - df: DataFrame 包含 date 和 m1b_money_supply 欄位
        
        回傳:
        - DataFrame 新增 m1b_mom 欄位
        """
        if df.empty or 'm1b_money_supply' not in df.columns:
            return df
        
        result_df = df.copy()
        
        # 保存原始日期格式（如果還沒有保存）
        if 'date_orig' not in result_df.columns:
            result_df['date_orig'] = result_df['date'].copy()
        
        # 確保日期格式正確並排序（用於計算）
        if 'date_parsed' in result_df.columns:
            result_df['date_parsed'] = pd.to_datetime(result_df['date_parsed'], format='%Y%m%d', errors='coerce')
        else:
            if 'date' in result_df.columns:
                result_df['date_parsed'] = pd.to_datetime(result_df['date'], format='%Y%m%d', errors='coerce')
            else:
                result_df['date_parsed'] = pd.to_datetime(result_df['date_orig'], format='%Y%m%d', errors='coerce')
        
        result_df = result_df.sort_values('date_parsed').reset_index(drop=True)
        
        # 新增年份和月份欄位
        result_df['year'] = result_df['date_parsed'].dt.year
        result_df['month'] = result_df['date_parsed'].dt.month
        
        # 按年份和月份分組，取得每個月的 M1B 值（同一月的所有交易日使用相同值）
        monthly_data = result_df.groupby(['year', 'month'])['m1b_money_supply'].first().reset_index()
        monthly_data.columns = ['year', 'month', 'm1b_value']
        
        # 計算月對月變化率
        mom_values = []
        
        for idx, row in result_df.iterrows():
            current_year = row['year']
            current_month = row['month']
            current_m1b = row['m1b_money_supply']
            
            if pd.isna(current_m1b):
                mom_values.append(None)
                continue
            
            # 計算上一個月的年份和月份
            if current_month == 1:
                prev_year = current_year - 1
                prev_month = 12
            else:
                prev_year = current_year
                prev_month = current_month - 1
            
            # 找上一個月的 M1B 值
            prev_month_data = monthly_data[
                (monthly_data['year'] == prev_year) &
                (monthly_data['month'] == prev_month)
            ]
            
            if not prev_month_data.empty and not pd.isna(prev_month_data.iloc[0]['m1b_value']):
                prev_m1b = prev_month_data.iloc[0]['m1b_value']
                if prev_m1b != 0:
                    # 計算月對月變化率：(當月 - 上月) / 上月 * 100
                    mom = ((current_m1b - prev_m1b) / prev_m1b) * 100
                    mom_values.append(mom)
                else:
                    mom_values.append(None)
            else:
                mom_values.append(None)
        
        result_df['m1b_mom'] = mom_values
        
        # 移除臨時欄位（保留 date_orig 和原始 date）
        result_df = result_df.drop(columns=['year', 'month', 'date_parsed'], errors='ignore')
        
        return result_df
    
    def calculate_m1b_vs_3m_avg(self, df):
        """
        計算當月 M1B 與前三個月平均的變化率
        
        參數:
        - df: DataFrame 包含 date 和 m1b_money_supply 欄位
        
        回傳:
        - DataFrame 新增 m1b_vs_3m_avg 欄位
        """
        if df.empty or 'm1b_money_supply' not in df.columns:
            return df
        
        result_df = df.copy()
        
        # 保存原始日期格式（如果還沒有保存）
        if 'date_orig' not in result_df.columns:
            result_df['date_orig'] = result_df['date'].copy()
        
        # 確保日期格式正確並排序（用於計算）
        if 'date_parsed' in result_df.columns:
            result_df['date_parsed'] = pd.to_datetime(result_df['date_parsed'], format='%Y%m%d', errors='coerce')
        else:
            if 'date' in result_df.columns:
                result_df['date_parsed'] = pd.to_datetime(result_df['date'], format='%Y%m%d', errors='coerce')
            else:
                result_df['date_parsed'] = pd.to_datetime(result_df['date_orig'], format='%Y%m%d', errors='coerce')
        
        result_df = result_df.sort_values('date_parsed').reset_index(drop=True)
        
        # 新增年份和月份欄位
        result_df['year'] = result_df['date_parsed'].dt.year
        result_df['month'] = result_df['date_parsed'].dt.month
        
        # 按年份和月份分組，取得每個月的 M1B 值（同一月的所有交易日使用相同值）
        monthly_data = result_df.groupby(['year', 'month'])['m1b_money_supply'].first().reset_index()
        monthly_data.columns = ['year', 'month', 'm1b_value']
        monthly_data = monthly_data.sort_values(['year', 'month']).reset_index(drop=True)
        
        # 計算當月 M1B vs 前三個月平均
        vs_3m_avg_values = []
        
        for idx, row in result_df.iterrows():
            current_year = row['year']
            current_month = row['month']
            current_m1b = row['m1b_money_supply']
            
            if pd.isna(current_m1b):
                vs_3m_avg_values.append(None)
                continue
            
            # 計算前三個月的年份和月份
            prev_months = []
            for i in range(1, 4):  # 前1個月、前2個月、前3個月
                if current_month > i:
                    prev_year = current_year
                    prev_month = current_month - i
                else:
                    # 跨年處理
                    months_to_subtract = i - current_month
                    prev_year = current_year - 1
                    prev_month = 12 - months_to_subtract
                prev_months.append((prev_year, prev_month))
            
            # 取得前三個月的 M1B 值
            prev_m1b_values = []
            for prev_year, prev_month in prev_months:
                prev_month_data = monthly_data[
                    (monthly_data['year'] == prev_year) &
                    (monthly_data['month'] == prev_month)
                ]
                
                if not prev_month_data.empty and not pd.isna(prev_month_data.iloc[0]['m1b_value']):
                    prev_m1b_values.append(prev_month_data.iloc[0]['m1b_value'])
            
            # 如果前三個月的資料都齊全，計算平均值和變化率
            if len(prev_m1b_values) == 3:
                avg_3m = sum(prev_m1b_values) / 3
                if avg_3m != 0:
                    # 計算變化率：(當月 - 前三個月平均) / 前三個月平均 * 100
                    vs_3m_avg = ((current_m1b - avg_3m) / avg_3m) * 100
                    vs_3m_avg_values.append(vs_3m_avg)
                else:
                    vs_3m_avg_values.append(None)
            else:
                vs_3m_avg_values.append(None)
        
        result_df['m1b_vs_3m_avg'] = vs_3m_avg_values
        
        # 移除臨時欄位（保留 date_orig 和原始 date）
        result_df = result_df.drop(columns=['year', 'month', 'date_parsed'], errors='ignore')
        
        return result_df
    
    def calculate_and_update(self, db_manager):
        """
        從資料庫讀取資料，計算年增率並更新資料庫
        
        參數:
        - db_manager: DatabaseManager 實例
        
        回傳:
        - dict 包含更新統計資訊
        """
        print("[Info] 開始計算 M1B 年增率...")
        
        try:
            # 確保欄位存在（在計算前先檢查並新增）
            print("[Info] 確保資料表欄位存在...")
            db_manager.ensure_table_column('leading_indicators_data', 'm1b_yoy_month', 'REAL')
            db_manager.ensure_table_column('leading_indicators_data', 'm1b_yoy_momentum', 'REAL')
            db_manager.ensure_table_column('leading_indicators_data', 'm1b_mom', 'REAL')
            db_manager.ensure_table_column('leading_indicators_data', 'm1b_vs_3m_avg', 'REAL')
            
            # 清空舊的年增率動能欄位數值（只清空這個欄位，不影響其他資料）
            print("[Info] 清空舊的年增率動能欄位數值...")
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            try:
                # 檢查是否有舊的 m1b_yoy_rolling_12m 欄位，如果有則清空
                cursor.execute("PRAGMA table_info(leading_indicators_data)")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                # 清空新的動能欄位和月對月變化率欄位
                cursor.execute("UPDATE leading_indicators_data SET m1b_yoy_momentum = NULL")
                cursor.execute("UPDATE leading_indicators_data SET m1b_mom = NULL")
                cursor.execute("UPDATE leading_indicators_data SET m1b_vs_3m_avg = NULL")
                
                # 如果存在舊的滾動12個月欄位，也清空它（用戶可能想清除舊資料）
                if 'm1b_yoy_rolling_12m' in column_names:
                    cursor.execute("UPDATE leading_indicators_data SET m1b_yoy_rolling_12m = NULL")
                    print("[Info] 已清空 m1b_yoy_rolling_12m 欄位數值（舊欄位）")
                
                conn.commit()
                print("[Info] 已清空 m1b_yoy_momentum、m1b_mom 和 m1b_vs_3m_avg 欄位數值")
            except Exception as e:
                # 如果欄位不存在，稍後會自動新增
                print(f"[Warning] 清空欄位時發生錯誤（可能是欄位不存在）: {e}")
                conn.rollback()
            finally:
                conn.close()
            
            # 從資料庫讀取資料（包含 2014 年的資料用於計算基準）
            query = "SELECT date, m1b_money_supply FROM leading_indicators_data WHERE m1b_money_supply IS NOT NULL ORDER BY date"
            df = db_manager.execute_query_dataframe(query)
            
            if df.empty:
                print("[Warning] 找不到 M1B 資料")
                return {
                    'yoy_month_count': 0,
                    'yoy_momentum_count': 0,
                    'mom_count': 0,
                    'vs_3m_avg_count': 0,
                    'error': '找不到資料'
                }
            
            print(f"[Info] 讀取 {len(df)} 筆資料")
            
            # 保存原始日期格式（YYYYMMDD 字串）
            df['date_orig'] = df['date'].copy()
            
            # 計算月對月年增率（需要 2014 年資料作為基準）
            print("[Info] 計算月對月年增率...")
            df_with_month = self.calculate_yoy_month(df.copy())
            
            # 計算月對月變化率（需要先有原始資料）
            print("[Info] 計算月對月變化率...")
            df_with_mom = self.calculate_m1b_mom(df.copy())
            
            # 計算當月 vs 前三個月平均（需要先有原始資料）
            print("[Info] 計算當月 M1B vs 前三個月平均...")
            df_with_3m_avg = self.calculate_m1b_vs_3m_avg(df.copy())
            
            # 合併資料：將 MOM 和 3M_AVG 合併到年增率 DataFrame
            # 確保 date_orig 欄位存在（calculate_yoy_month 應該已經創建了它）
            if 'date_orig' not in df_with_month.columns:
                df_with_month['date_orig'] = df_with_month['date'].copy() if 'date' in df_with_month.columns else df_with_month.index.astype(str)
            
            # 合併 MOM 資料到年增率 DataFrame（使用 date_orig 作為合併鍵）
            df_with_mom_cols = df_with_mom[['date_orig', 'm1b_mom']].copy()
            df_with_3m_avg_cols = df_with_3m_avg[['date_orig', 'm1b_vs_3m_avg']].copy()
            
            df_with_both = df_with_month.merge(df_with_mom_cols, on='date_orig', how='left')
            df_with_both = df_with_both.merge(df_with_3m_avg_cols, on='date_orig', how='left')
            
            # 計算年增率動能（需要先有年增率資料）
            print("[Info] 計算年增率動能...")
            df_with_both = self.calculate_yoy_momentum(df_with_both)
            
            # 更新資料庫
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            updated_month_count = 0
            updated_momentum_count = 0
            updated_mom_count = 0
            updated_vs_3m_avg_count = 0
            
            try:
                for idx, row in df_with_both.iterrows():
                    # 使用原始日期格式（YYYYMMDD 字串）
                    date_str = row.get('date_orig', row.get('date'))
                    if isinstance(date_str, pd.Timestamp):
                        date_str = date_str.strftime('%Y%m%d')
                    elif not isinstance(date_str, str):
                        continue
                    
                    yoy_month = row.get('m1b_yoy_month')
                    yoy_momentum = row.get('m1b_yoy_momentum')
                    m1b_mom = row.get('m1b_mom')
                    m1b_vs_3m_avg = row.get('m1b_vs_3m_avg')
                    
                    # 更新月對月年增率
                    if not pd.isna(yoy_month):
                        cursor.execute(
                            "UPDATE leading_indicators_data SET m1b_yoy_month = ? WHERE date = ?",
                            (float(yoy_month), date_str)
                        )
                        updated_month_count += 1
                    
                    # 更新年增率動能
                    if not pd.isna(yoy_momentum):
                        cursor.execute(
                            "UPDATE leading_indicators_data SET m1b_yoy_momentum = ? WHERE date = ?",
                            (float(yoy_momentum), date_str)
                        )
                        updated_momentum_count += 1
                    
                    # 更新月對月變化率
                    if not pd.isna(m1b_mom):
                        cursor.execute(
                            "UPDATE leading_indicators_data SET m1b_mom = ? WHERE date = ?",
                            (float(m1b_mom), date_str)
                        )
                        updated_mom_count += 1
                    
                    # 更新當月 vs 前三個月平均
                    if not pd.isna(m1b_vs_3m_avg):
                        cursor.execute(
                            "UPDATE leading_indicators_data SET m1b_vs_3m_avg = ? WHERE date = ?",
                            (float(m1b_vs_3m_avg), date_str)
                        )
                        updated_vs_3m_avg_count += 1
                
                conn.commit()
                print(f"[Info] 資料庫更新完成")
                print(f"  - 月對月年增率：更新 {updated_month_count} 筆")
                print(f"  - 年增率動能：更新 {updated_momentum_count} 筆")
                print(f"  - 月對月變化率：更新 {updated_mom_count} 筆")
                print(f"  - 當月 vs 前三個月平均：更新 {updated_vs_3m_avg_count} 筆")
                
                return {
                    'yoy_month_count': updated_month_count,
                    'yoy_momentum_count': updated_momentum_count,
                    'mom_count': updated_mom_count,
                    'vs_3m_avg_count': updated_vs_3m_avg_count,
                    'success': True
                }
                
            except Exception as e:
                conn.rollback()
                print(f"[Error] 更新資料庫失敗: {e}")
                import traceback
                traceback.print_exc()
                return {
                    'yoy_month_count': 0,
                    'yoy_momentum_count': 0,
                    'mom_count': 0,
                    'vs_3m_avg_count': 0,
                    'error': str(e)
                }
            finally:
                conn.close()
                
        except Exception as e:
            print(f"[Error] 計算 M1B 年增率失敗: {e}")
            import traceback
            traceback.print_exc()
            return {
                'yoy_month_count': 0,
                'yoy_momentum_count': 0,
                'error': str(e)
            }

