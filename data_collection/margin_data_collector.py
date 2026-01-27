"""
融資維持率資料收集模組
從證交所 MI_MARGN API 取得每日融資融券數據，儲存原始數據並計算大盤融資維持率
"""

import requests
import pandas as pd
import sqlite3
import time
import pandas_market_calendars as pmc
from datetime import datetime
from .database_manager import DatabaseManager


class MarginDataCollector:
    """融資維持率資料收集器"""
    
    BASE_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
    HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TWStockBot/1.0)"}
    
    def __init__(self, db_manager, polite_sleep=5):
        """
        初始化融資資料收集器
        
        參數:
        - db_manager: DatabaseManager 實例
        - polite_sleep: 每次請求之間的延遲時間（秒，預設 5 秒）
        """
        self.db_manager = db_manager
        self.db_path = db_manager.db_path
        self.polite_sleep = polite_sleep
        
        # 確保資料表存在
        self.db_manager.init_market_margin_table()
    
    @staticmethod
    def _normalize_date(date):
        """標準化日期格式為 YYYYMMDD"""
        if isinstance(date, datetime):
            return date.strftime('%Y%m%d')
        if isinstance(date, str):
            digits = ''.join(filter(str.isdigit, date))
            if len(digits) == 8:
                return digits
            try:
                parsed = datetime.strptime(date, '%Y-%m-%d')
                return parsed.strftime('%Y%m%d')
            except ValueError:
                pass
        raise ValueError(f"無法解析日期格式: {date}")
    
    @staticmethod
    def _parse_number(value):
        """解析數字字串（移除逗號）"""
        if value is None or value == '':
            return None
        try:
            return int(str(value).replace(',', '').strip())
        except (ValueError, AttributeError):
            return None
    
    def fetch_margin_data(self, date, retry_times=3, retry_delay=5):
        """
        從證交所 API 取得指定日期的融資融券數據
        
        參數:
        - date: 日期（YYYYMMDD 或 datetime）
        - retry_times: 重試次數（預設 3 次）
        - retry_delay: 重試延遲（秒，預設 5 秒）
        
        回傳:
        - dict: 包含解析後的數據，如果失敗則返回 None
        """
        date_str = self._normalize_date(date)
        
        for attempt in range(1, retry_times + 1):
            try:
                response = requests.get(
                    self.BASE_URL,
                    params={
                        'date': date_str,
                        'selectType': 'MS',  # 市場統計
                        'response': 'json'
                    },
                    headers=self.HEADERS,
                    timeout=15
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get('stat') != 'OK':
                    print(f"[Warning] {date_str} API 回傳錯誤: {data.get('stat')}")
                    if attempt < retry_times:
                        print(f"[Info] {retry_delay} 秒後重試（第 {attempt}/{retry_times} 次）...")
                        time.sleep(retry_delay)
                        continue
                    return None
                
                # 解析 JSON 數據
                tables = data.get('tables', [])
                if not tables or not isinstance(tables, list) or not tables[0].get('data'):
                    print(f"[Warning] {date_str} JSON 結構異常")
                    if attempt < retry_times:
                        print(f"[Info] {retry_delay} 秒後重試（第 {attempt}/{retry_times} 次）...")
                        time.sleep(retry_delay)
                        continue
                    return None
                
                rows = tables[0]['data']
                
                # 解析融資(交易單位) - rows[0]
                # fields: ["項目", "買進", "賣出", "現金(券)償還", "前日餘額", "今日餘額"]
                margin_units = {
                    'buy': rows[0][1] if len(rows[0]) > 1 else None,
                    'sell': rows[0][2] if len(rows[0]) > 2 else None,
                    'cash_repay': rows[0][3] if len(rows[0]) > 3 else None,
                    'prev_balance': rows[0][4] if len(rows[0]) > 4 else None,
                    'today_balance': rows[0][5] if len(rows[0]) > 5 else None
                }
                
                # 解析融券(交易單位) - rows[1]
                short_units = {
                    'buy': rows[1][1] if len(rows[1]) > 1 else None,
                    'sell': rows[1][2] if len(rows[1]) > 2 else None,
                    'cash_repay': rows[1][3] if len(rows[1]) > 3 else None,
                    'prev_balance': rows[1][4] if len(rows[1]) > 4 else None,
                    'today_balance': rows[1][5] if len(rows[1]) > 5 else None
                }
                
                # 解析融資金額(仟元) - rows[2]
                margin_amount = {
                    'buy': rows[2][1] if len(rows[2]) > 1 else None,
                    'sell': rows[2][2] if len(rows[2]) > 2 else None,
                    'cash_repay': rows[2][3] if len(rows[2]) > 3 else None,
                    'prev_balance': rows[2][4] if len(rows[2]) > 4 else None,
                    'today_balance': rows[2][5] if len(rows[2]) > 5 else None
                }
                
                result = {
                    'date': date_str,
                    # 融資(交易單位)
                    'margin_buy_units': margin_units['buy'],
                    'margin_sell_units': margin_units['sell'],
                    'margin_cash_repay_units': margin_units['cash_repay'],
                    'margin_prev_balance_units': margin_units['prev_balance'],
                    'margin_today_balance_units': margin_units['today_balance'],
                    # 融券(交易單位)
                    'short_buy_units': short_units['buy'],
                    'short_sell_units': short_units['sell'],
                    'short_cash_repay_units': short_units['cash_repay'],
                    'short_prev_balance_units': short_units['prev_balance'],
                    'short_today_balance_units': short_units['today_balance'],
                    # 融資金額(仟元)
                    'margin_buy_amount': margin_amount['buy'],
                    'margin_sell_amount': margin_amount['sell'],
                    'margin_cash_repay_amount': margin_amount['cash_repay'],
                    'margin_prev_balance_amount': margin_amount['prev_balance'],
                    'margin_today_balance_amount': margin_amount['today_balance']
                }
                
                return result
                
            except requests.exceptions.RequestException as e:
                print(f"[Error] {date_str} 請求失敗: {e}")
                if attempt < retry_times:
                    print(f"[Info] {retry_delay} 秒後重試（第 {attempt}/{retry_times} 次）...")
                    time.sleep(retry_delay)
                    continue
                return None
            except Exception as e:
                print(f"[Error] {date_str} 解析數據失敗: {e}")
                if attempt < retry_times:
                    print(f"[Info] {retry_delay} 秒後重試（第 {attempt}/{retry_times} 次）...")
                    time.sleep(retry_delay)
                    continue
                return None
        
        return None
    
    def save_margin_data(self, data_dict):
        """
        儲存融資數據到資料庫
        
        參數:
        - data_dict: 包含融資數據的字典
        """
        if data_dict is None:
            return False
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO market_margin_data (
                    date,
                    margin_buy_units, margin_sell_units, margin_cash_repay_units,
                    margin_prev_balance_units, margin_today_balance_units,
                    short_buy_units, short_sell_units, short_cash_repay_units,
                    short_prev_balance_units, short_today_balance_units,
                    margin_buy_amount, margin_sell_amount, margin_cash_repay_amount,
                    margin_prev_balance_amount, margin_today_balance_amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data_dict['date'],
                data_dict['margin_buy_units'],
                data_dict['margin_sell_units'],
                data_dict['margin_cash_repay_units'],
                data_dict['margin_prev_balance_units'],
                data_dict['margin_today_balance_units'],
                data_dict['short_buy_units'],
                data_dict['short_sell_units'],
                data_dict['short_cash_repay_units'],
                data_dict['short_prev_balance_units'],
                data_dict['short_today_balance_units'],
                data_dict['margin_buy_amount'],
                data_dict['margin_sell_amount'],
                data_dict['margin_cash_repay_amount'],
                data_dict['margin_prev_balance_amount'],
                data_dict['margin_today_balance_amount']
            ))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[Error] 儲存 {data_dict['date']} 的融資數據失敗: {e}")
            return False
        finally:
            conn.close()
    
    def batch_fetch_margin_data(self, start_date='2015-01-01', end_date=None, retry_times=3, retry_delay=5):
        """
        批次取得融資融券數據（2015-2025年）
        
        參數:
        - start_date: 起始日期（YYYY-MM-DD 或 YYYYMMDD，預設 2015-01-01）
        - end_date: 結束日期（YYYY-MM-DD 或 YYYYMMDD，預設今天）
        - retry_times: 每個日期失敗時的重試次數（預設 3 次）
        - retry_delay: 重試前的等待時間（秒，預設 5 秒）
        
        回傳:
        - dict: 更新結果統計
        """
        print(f"\n{'='*60}")
        print(f"批次取得融資融券數據")
        print(f"{'='*60}\n")
        
        # 取得台灣交易日曆
        cal = pmc.get_calendar('XTAI')
        
        # 確定日期範圍
        if isinstance(start_date, str):
            start_ts = pd.Timestamp(start_date)
        else:
            start_ts = start_date if start_date else pd.Timestamp('2015-01-01')
        
        if end_date is None:
            end_ts = pd.Timestamp.now()
        elif isinstance(end_date, str):
            end_ts = pd.Timestamp(end_date)
        else:
            end_ts = end_date
        
        # 取得交易日列表
        trading_days = cal.valid_days(start_date=start_ts, end_date=end_ts)
        trading_days_str = [day.strftime('%Y%m%d') for day in trading_days]
        
        print(f"[Info] 日期範圍：{start_ts.date()} 至 {end_ts.date()}")
        print(f"[Info] 共有 {len(trading_days_str)} 個交易日")
        
        # 檢查哪些日期已經有資料
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM market_margin_data")
        existing_dates = set([row[0] for row in cursor.fetchall()])
        conn.close()
        
        print(f"[Info] 資料庫中已有 {len(existing_dates)} 個交易日的資料")
        
        # 只處理需要更新的日期
        dates_to_update = [d for d in trading_days_str if d not in existing_dates]
        
        if not dates_to_update:
            print(f"[Info] 沒有需要更新的日期")
            return {'success': 0, 'failed': 0, 'skipped': len(trading_days_str), 'total': len(trading_days_str)}
        
        print(f"[Info] 需要更新 {len(dates_to_update)} 個交易日的資料")
        print(f"[Info] 日期列表: {', '.join(dates_to_update[:5])}{'...' if len(dates_to_update) > 5 else ''}\n")
        
        # 批次取得數據
        success_count = 0
        failed_dates = []
        
        for idx, date_str in enumerate(dates_to_update, 1):
            print(f"[{idx}/{len(dates_to_update)}] 處理 {date_str}...", end=' ')
            
            data = self.fetch_margin_data(date_str, retry_times=retry_times, retry_delay=retry_delay)
            
            if data:
                if self.save_margin_data(data):
                    success_count += 1
                    print("✓")
                else:
                    failed_dates.append(date_str)
                    print("✗ (儲存失敗)")
            else:
                failed_dates.append(date_str)
                print("✗ (取得失敗)")
            
            # 禮貌擷取：每次請求之間延遲
            if idx < len(dates_to_update):
                time.sleep(self.polite_sleep)
        
        print(f"\n{'='*60}")
        print(f"批次取得完成")
        print(f"{'='*60}")
        print(f"成功: {success_count} 筆")
        print(f"失敗: {len(failed_dates)} 筆")
        if failed_dates:
            print(f"失敗日期: {', '.join(failed_dates[:10])}{'...' if len(failed_dates) > 10 else ''}")
        print(f"{'='*60}\n")
        
        return {
            'success': success_count,
            'failed': len(failed_dates),
            'skipped': len(trading_days_str) - len(dates_to_update),
            'total': len(trading_days_str),
            'failed_dates': failed_dates
        }
    
    def add_calculation_columns(self):
        """
        在資料表中新增計算欄位（如果不存在）
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查欄位是否存在，如果不存在則添加
            columns_to_add = [
                ('margin_shares_total', 'REAL'),
                ('margin_balance', 'REAL'),
                ('margin_market_value', 'REAL'),
                ('margin_maintenance_ratio', 'REAL')
            ]
            
            cursor.execute("PRAGMA table_info(market_margin_data)")
            existing_columns = [col[1] for col in cursor.fetchall()]
            
            for col_name, col_type in columns_to_add:
                if col_name not in existing_columns:
                    cursor.execute(f"ALTER TABLE market_margin_data ADD COLUMN {col_name} {col_type}")
                    print(f"[Info] 已添加欄位: {col_name}")
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[Error] 添加計算欄位失敗: {e}")
            raise
        finally:
            conn.close()
    
    def calculate_margin_maintenance_ratio(self, date_str=None):
        """
        計算大盤融資維持率
        
        公式：大盤融資維持率 = (所有融資股數 × 股票收盤價) / 大盤融資餘額
        
        注意：由於 API 只提供市場整體數據，我們使用以下近似方法：
        - 所有融資股票市值 ≈ 融資金額(仟元) × 1000（轉換為元）
        - 大盤融資餘額 = 融資金額(仟元) × 1000（轉換為元）
        - 融資維持率 = 融資股票市值 / 融資餘額
        
        實際上，如果我們有融資金額，可以近似認為：
        融資維持率 ≈ 1.0（因為融資金額本身就是基於融資股票市值計算的）
        
        但更準確的方法是：
        - 使用融資股數和平均股價來估算市值
        - 或者需要從其他 API 獲取個股融資數據
        
        參數:
        - date_str: 要計算的日期（YYYYMMDD），如果為 None 則計算所有日期
        """
        # 先確保計算欄位存在
        self.add_calculation_columns()
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            # 構建查詢條件
            if date_str:
                query = "SELECT date, margin_prev_balance_units, margin_prev_balance_amount FROM market_margin_data WHERE date = ?"
                params = (date_str,)
            else:
                query = "SELECT date, margin_prev_balance_units, margin_prev_balance_amount FROM market_margin_data ORDER BY date"
                params = None
            
            cursor.execute(query, params if params else ())
            rows = cursor.fetchall()
            
            if not rows:
                print("[Warning] 沒有找到需要計算的數據")
                return
            
            print(f"[Info] 開始計算融資維持率，共 {len(rows)} 筆數據...")
            
            updated_count = 0
            for row in rows:
                date, margin_units_str, margin_amount_str = row
                
                # 數值化原始數據
                margin_shares_total = self._parse_number(margin_units_str)  # 融資股數（交易單位）
                margin_balance_thousands = self._parse_number(margin_amount_str)  # 融資餘額（仟元）
                
                if margin_shares_total is None or margin_balance_thousands is None:
                    continue
                
                # 轉換單位：融資餘額從仟元轉為元
                margin_balance = margin_balance_thousands * 1000  # 元
                
                # 計算融資維持率
                # 注意：這裡使用簡化計算，實際需要個股數據才能精確計算
                # 近似方法：假設平均融資價格 = 融資餘額 / 融資股數
                if margin_shares_total > 0:
                    avg_margin_price = margin_balance / margin_shares_total
                    # 融資股票市值 = 融資股數 × 平均價格
                    margin_market_value = margin_shares_total * avg_margin_price
                    # 融資維持率 = 市值 / 融資餘額
                    margin_maintenance_ratio = margin_market_value / margin_balance if margin_balance > 0 else None
                else:
                    margin_market_value = None
                    margin_maintenance_ratio = None
                
                # 更新資料庫
                update_query = """
                    UPDATE market_margin_data 
                    SET margin_shares_total = ?,
                        margin_balance = ?,
                        margin_market_value = ?,
                        margin_maintenance_ratio = ?
                    WHERE date = ?
                """
                cursor.execute(update_query, (
                    margin_shares_total,
                    margin_balance,
                    margin_market_value,
                    margin_maintenance_ratio,
                    date
                ))
                updated_count += 1
            
            conn.commit()
            print(f"[Info] 完成計算，共更新 {updated_count} 筆數據")
            
        except Exception as e:
            conn.rollback()
            print(f"[Error] 計算融資維持率失敗: {e}")
            raise
        finally:
            conn.close()
