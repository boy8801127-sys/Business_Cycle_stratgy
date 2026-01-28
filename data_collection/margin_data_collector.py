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
    
    def add_derived_columns(self):
        """
        在資料表中新增衍生指標欄位（如果不存在）
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查欄位是否存在，如果不存在則添加
            columns_to_add = [
                # 券資比
                ('short_margin_ratio', 'REAL'),
                # 融資相關衍生指標
                ('margin_balance_change_rate', 'REAL'),
                ('margin_balance_net_change', 'REAL'),
                ('margin_buy_sell_ratio', 'REAL'),
                ('margin_buy_sell_net', 'REAL'),
                # 融券相關衍生指標
                ('short_balance_change_rate', 'REAL'),
                ('short_balance_net_change', 'REAL'),
                ('short_buy_sell_ratio', 'REAL'),
                ('short_buy_sell_net', 'REAL')
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
            print(f"[Error] 添加衍生指標欄位失敗: {e}")
            raise
        finally:
            conn.close()
    
    def calculate_derived_indicators(self, date_str=None):
        """
        計算所有衍生指標
        
        參數:
        - date_str: 要計算的日期（YYYYMMDD），如果為 None 則計算所有日期
        """
        # 先確保衍生指標欄位存在
        self.add_derived_columns()
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            # 構建查詢條件
            if date_str:
                query = """
                    SELECT date,
                        margin_prev_balance_amount, margin_today_balance_amount,
                        margin_buy_amount, margin_sell_amount,
                        short_prev_balance_units, short_today_balance_units,
                        margin_today_balance_units,
                        short_buy_units, short_sell_units
                    FROM market_margin_data 
                    WHERE date = ?
                """
                params = (date_str,)
            else:
                query = """
                    SELECT date,
                        margin_prev_balance_amount, margin_today_balance_amount,
                        margin_buy_amount, margin_sell_amount,
                        short_prev_balance_units, short_today_balance_units,
                        margin_today_balance_units,
                        short_buy_units, short_sell_units
                    FROM market_margin_data 
                    ORDER BY date
                """
                params = None
            
            cursor.execute(query, params if params else ())
            rows = cursor.fetchall()
            
            if not rows:
                print("[Warning] 沒有找到需要計算的數據")
                return
            
            print(f"[Info] 開始計算衍生指標，共 {len(rows)} 筆數據...")
            
            updated_count = 0
            for row in rows:
                date = row[0]
                margin_prev_balance_amount_str = row[1]
                margin_today_balance_amount_str = row[2]
                margin_buy_amount_str = row[3]
                margin_sell_amount_str = row[4]
                short_prev_balance_units_str = row[5]
                short_today_balance_units_str = row[6]
                margin_today_balance_units_str = row[7]
                short_buy_units_str = row[8]
                short_sell_units_str = row[9]
                
                # 數值化原始數據
                margin_prev_balance_amount = self._parse_number(margin_prev_balance_amount_str)
                margin_today_balance_amount = self._parse_number(margin_today_balance_amount_str)
                margin_buy_amount = self._parse_number(margin_buy_amount_str)
                margin_sell_amount = self._parse_number(margin_sell_amount_str)
                short_prev_balance_units = self._parse_number(short_prev_balance_units_str)
                short_today_balance_units = self._parse_number(short_today_balance_units_str)
                margin_today_balance_units = self._parse_number(margin_today_balance_units_str)
                short_buy_units = self._parse_number(short_buy_units_str)
                short_sell_units = self._parse_number(short_sell_units_str)
                
                # 計算券資比
                if margin_today_balance_units and margin_today_balance_units > 0:
                    short_margin_ratio = short_today_balance_units / margin_today_balance_units if short_today_balance_units else None
                else:
                    short_margin_ratio = None
                
                # 計算融資餘額變化率
                if margin_prev_balance_amount and margin_prev_balance_amount > 0:
                    margin_balance_change_rate = (margin_today_balance_amount - margin_prev_balance_amount) / margin_prev_balance_amount if margin_today_balance_amount is not None else None
                else:
                    margin_balance_change_rate = None
                
                # 計算融資餘額淨增減
                if margin_today_balance_amount is not None and margin_prev_balance_amount is not None:
                    margin_balance_net_change = margin_today_balance_amount - margin_prev_balance_amount
                else:
                    margin_balance_net_change = None
                
                # 計算融資買賣比
                if margin_sell_amount and margin_sell_amount > 0:
                    margin_buy_sell_ratio = margin_buy_amount / margin_sell_amount if margin_buy_amount else None
                else:
                    margin_buy_sell_ratio = None
                
                # 計算融資買賣淨額
                if margin_buy_amount is not None and margin_sell_amount is not None:
                    margin_buy_sell_net = margin_buy_amount - margin_sell_amount
                else:
                    margin_buy_sell_net = None
                
                # 計算融券餘額變化率
                if short_prev_balance_units and short_prev_balance_units > 0:
                    short_balance_change_rate = (short_today_balance_units - short_prev_balance_units) / short_prev_balance_units if short_today_balance_units is not None else None
                else:
                    short_balance_change_rate = None
                
                # 計算融券餘額淨增減
                if short_today_balance_units is not None and short_prev_balance_units is not None:
                    short_balance_net_change = short_today_balance_units - short_prev_balance_units
                else:
                    short_balance_net_change = None
                
                # 計算融券買賣比
                if short_buy_units and short_buy_units > 0:
                    short_buy_sell_ratio = short_sell_units / short_buy_units if short_sell_units else None
                else:
                    short_buy_sell_ratio = None
                
                # 計算融券買賣淨額
                if short_sell_units is not None and short_buy_units is not None:
                    short_buy_sell_net = short_sell_units - short_buy_units
                else:
                    short_buy_sell_net = None
                
                # 更新資料庫
                update_query = """
                    UPDATE market_margin_data 
                    SET short_margin_ratio = ?,
                        margin_balance_change_rate = ?,
                        margin_balance_net_change = ?,
                        margin_buy_sell_ratio = ?,
                        margin_buy_sell_net = ?,
                        short_balance_change_rate = ?,
                        short_balance_net_change = ?,
                        short_buy_sell_ratio = ?,
                        short_buy_sell_net = ?
                    WHERE date = ?
                """
                cursor.execute(update_query, (
                    short_margin_ratio,
                    margin_balance_change_rate,
                    margin_balance_net_change,
                    margin_buy_sell_ratio,
                    margin_buy_sell_net,
                    short_balance_change_rate,
                    short_balance_net_change,
                    short_buy_sell_ratio,
                    short_buy_sell_net,
                    date
                ))
                updated_count += 1
            
            conn.commit()
            print(f"[Info] 完成計算，共更新 {updated_count} 筆數據")
            
        except Exception as e:
            conn.rollback()
            print(f"[Error] 計算衍生指標失敗: {e}")
            raise
        finally:
            conn.close()
    
    def migrate_remove_old_columns(self):
        """
        遷移資料表，移除舊的計算欄位（margin_shares_total, margin_balance, margin_market_value, margin_maintenance_ratio）
        
        注意：SQLite 不支援直接刪除欄位，因此採用「建立新表 + 遷移資料 + 刪除舊表」的方式
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查是否有舊欄位存在
            cursor.execute("PRAGMA table_info(market_margin_data)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            old_columns = ['margin_shares_total', 'margin_balance', 'margin_market_value', 'margin_maintenance_ratio']
            has_old_columns = any(col in column_names for col in old_columns)
            
            if not has_old_columns:
                print("[Info] 資料表中沒有需要移除的舊欄位")
                return
            
            print("[Info] 開始遷移資料表，移除舊的計算欄位...")
            
            # 建立新表（不包含舊欄位）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS market_margin_data_new (
                    date TEXT PRIMARY KEY,
                    margin_buy_units TEXT,
                    margin_sell_units TEXT,
                    margin_cash_repay_units TEXT,
                    margin_prev_balance_units TEXT,
                    margin_today_balance_units TEXT,
                    short_buy_units TEXT,
                    short_sell_units TEXT,
                    short_cash_repay_units TEXT,
                    short_prev_balance_units TEXT,
                    short_today_balance_units TEXT,
                    margin_buy_amount TEXT,
                    margin_sell_amount TEXT,
                    margin_cash_repay_amount TEXT,
                    margin_prev_balance_amount TEXT,
                    margin_today_balance_amount TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 遷移資料（排除舊欄位）
            cursor.execute('''
                INSERT INTO market_margin_data_new (
                    date,
                    margin_buy_units, margin_sell_units, margin_cash_repay_units,
                    margin_prev_balance_units, margin_today_balance_units,
                    short_buy_units, short_sell_units, short_cash_repay_units,
                    short_prev_balance_units, short_today_balance_units,
                    margin_buy_amount, margin_sell_amount, margin_cash_repay_amount,
                    margin_prev_balance_amount, margin_today_balance_amount,
                    created_at
                )
                SELECT 
                    date,
                    margin_buy_units, margin_sell_units, margin_cash_repay_units,
                    margin_prev_balance_units, margin_today_balance_units,
                    short_buy_units, short_sell_units, short_cash_repay_units,
                    short_prev_balance_units, short_today_balance_units,
                    margin_buy_amount, margin_sell_amount, margin_cash_repay_amount,
                    margin_prev_balance_amount, margin_today_balance_amount,
                    created_at
                FROM market_margin_data
            ''')
            
            # 刪除舊表
            cursor.execute("DROP TABLE market_margin_data")
            
            # 重新命名新表
            cursor.execute("ALTER TABLE market_margin_data_new RENAME TO market_margin_data")
            
            # 重新建立索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_margin_date ON market_margin_data(date)")
            
            conn.commit()
            print("[Info] 資料表遷移完成，舊欄位已移除")
            
        except Exception as e:
            conn.rollback()
            print(f"[Error] 資料表遷移失敗: {e}")
            # 如果失敗，嘗試刪除新表
            try:
                cursor.execute("DROP TABLE IF EXISTS market_margin_data_new")
            except:
                pass
            raise
        finally:
            conn.close()
