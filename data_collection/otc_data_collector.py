"""
上櫃股票資料蒐集模組
從櫃買中心 API 取得每日收盤行情
"""

import requests
import pandas as pd
import sqlite3
import time
import pandas_market_calendars as pmc
from datetime import datetime


class OTCDataCollector:
    """上櫃股票資料蒐集器"""
    
    BASE_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes"
    
    def __init__(self, db_manager, polite_sleep=5):
        self.db_manager = db_manager
        self.db_path = db_manager.db_path
        self.polite_sleep = polite_sleep
        self.session = requests.Session()
        self.db_manager.init_otc_stock_price_table()
    
    @staticmethod
    def _normalize_date(date):
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
    def _clean_field_name(field):
        return field.replace("'", "").replace(" ", "").strip()
    
    @staticmethod
    def _safe_float(value):
        if value is None or value == '':
            return None
        s = str(value).replace(',', '').replace('--', '0').replace('+', '').strip()
        if s in ('', '-'):
            return None
        try:
            return float(s)
        except ValueError:
            return None
    
    @staticmethod
    def _safe_int(value):
        float_val = OTCDataCollector._safe_float(value)
        if float_val is None:
            return None
        return int(float_val)
    
    def _build_field_map(self, fields):
        normalized = [self._clean_field_name(f) for f in fields]
        mapping = {}
        
        def find_index(candidates, fallback=None):
            for idx, name in enumerate(normalized):
                if any(candidate in name for candidate in candidates):
                    return idx
            return fallback
        
        mapping['ticker'] = find_index(['證券代號', '代號'], 0)
        mapping['stock_name'] = find_index(['證券名稱', '名稱'], 1)
        mapping['close'] = find_index(['收盤'], 2)
        mapping['change'] = find_index(['漲跌'], 3)
        mapping['open'] = find_index(['開盤'], 4)
        mapping['high'] = find_index(['最高'], 5)
        mapping['low'] = find_index(['最低'], 6)
        mapping['volume'] = find_index(['成交股數'], 8)
        mapping['turnover'] = find_index(['成交金額'], 9)
        
        return mapping
    
    def fetch_daily_quotes(self, date):
        date_str = self._normalize_date(date)
        query_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"
        
        try:
            resp = self.session.get(
                self.BASE_URL,
                params={'date': query_date, 'id': '', 'response': 'json'},
                headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.tpex.org.tw/'},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            print(f"[Error] 取得上櫃 {date_str} 資料失敗: {exc}")
            return pd.DataFrame()
        
        target_table = None
        for table in data.get('tables', []):
            title = (table.get('title') or '').strip()
            normalized_title = title.replace('\xa0', '')
            if '上櫃股票行情' in normalized_title or '上櫃' in normalized_title:
                target_table = table
                break
        if not target_table:
            # 嘗試以第一個含有 data 的表格作為 fallback
            for table in data.get('tables', []):
                if table.get('data'):
                    target_table = table
                    break
        
        if not target_table:
            print(f"[Warning] {date_str} 找不到上櫃收盤行情表格")
            return pd.DataFrame()
        
        fields = target_table.get('fields', [])
        field_map = self._build_field_map(fields)
        
        required = ['ticker', 'stock_name', 'close']
        if any(field_map.get(key) is None for key in required):
            print(f"[Error] {date_str} 上櫃資料缺少必要欄位")
            return pd.DataFrame()
        
        records = []
        data_rows = target_table.get('data', [])
        for row in data_rows:
            try:
                ticker = str(row[field_map['ticker']]).strip()
                stock_name = str(row[field_map['stock_name']]).strip()
            except (IndexError, TypeError):
                continue
            
            # 過濾權證：排除7開頭六位數的權證代號
            # 權證代號格式：7開頭，共6位數，全部為數字
            if len(ticker) == 6 and ticker.isdigit() and ticker.startswith('7'):
                continue  # 跳過權證
            
            close_value = self._safe_float(row[field_map['close']]) if field_map['close'] is not None else None
            if close_value is None:
                continue
            
            record = {
                'date': date_str,
                'stock_name': stock_name,
                'ticker': ticker,
                'open': self._safe_float(row[field_map['open']]) if field_map['open'] is not None and len(row) > field_map['open'] else None,
                'high': self._safe_float(row[field_map['high']]) if field_map['high'] is not None and len(row) > field_map['high'] else None,
                'low': self._safe_float(row[field_map['low']]) if field_map['low'] is not None and len(row) > field_map['low'] else None,
                'close': close_value,
                'volume': self._safe_int(row[field_map['volume']]) if field_map['volume'] is not None and len(row) > field_map['volume'] else None,
                'turnover': self._safe_float(row[field_map['turnover']]) if field_map['turnover'] is not None and len(row) > field_map['turnover'] else None,
                'change': self._safe_float(row[field_map['change']]) if field_map['change'] is not None and len(row) > field_map['change'] else None,
                'odd_lot_filled': 0
            }
            records.append(record)
        
        return pd.DataFrame(records)
    
    def save_otc_stock_price_data(self, df):
        if df is None or df.empty:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO tw_otc_stock_price_data
                    (date, stock_name, ticker, open, high, low, close, volume, turnover, change, odd_lot_filled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('date'),
                    row.get('stock_name'),
                    row.get('ticker'),
                    row.get('open'),
                    row.get('high'),
                    row.get('low'),
                    row.get('close'),
                    row.get('volume'),
                    row.get('turnover'),
                    row.get('change'),
                    row.get('odd_lot_filled', 0)
                ))
            conn.commit()
            print(f"[Info] 已儲存 {len(df)} 筆上櫃股票資料")
        except Exception as exc:
            conn.rollback()
            print(f"[Error] SQLite 儲存上櫃資料失敗: {exc}")
            raise
        finally:
            conn.close()
    
    def batch_fetch_otc_data(self, days=15, start_date=None, retry_times=3, retry_delay=5):
        print("\n" + "=" * 60)
        print(f"批次取得上櫃股票資料（目標：{days} 個交易日）")
        print("=" * 60 + "\n")
        
        cal = pmc.get_calendar('XTAI')
        
        if start_date is None:
            start_ts = pd.Timestamp('2015-01-01')
        else:
            if isinstance(start_date, str):
                digits = ''.join(filter(str.isdigit, start_date))
                if len(digits) == 8:
                    start_ts = pd.Timestamp(f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}")
                else:
                    start_ts = pd.Timestamp(start_date)
            else:
                start_ts = start_date
        
        today = pd.Timestamp.now()
        trading_days = cal.valid_days(start_date=start_ts, end_date=today)
        trading_days_str = [day.strftime('%Y%m%d') for day in trading_days]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM tw_otc_stock_price_data")
        existing_dates = set(row[0] for row in cursor.fetchall())
        conn.close()
        print(f"[Info] 上櫃資料庫已有 {len(existing_dates)} 個交易日")
        
        if days >= len(trading_days_str):
            dates_to_update = [d for d in trading_days_str if d not in existing_dates]
        else:
            dates_to_update = [d for d in trading_days_str[-days:] if d not in existing_dates]
        
        if not dates_to_update:
            print("[Info] 沒有需要更新的上櫃交易日")
            return {'success': 0, 'failed': 0, 'skipped': days, 'total': days}
        
        print(f"[Info] 需要更新 {len(dates_to_update)} 個上櫃交易日")
        success_count = 0
        failed_dates = []
        
        for idx, date_str in enumerate(dates_to_update, 1):
            print(f"[{idx}/{len(dates_to_update)}] 正在取得 {date_str} 上櫃資料...")
            success = False
            
            for attempt in range(1, retry_times + 1):
                df = self.fetch_daily_quotes(date_str)
                if not df.empty:
                    self.save_otc_stock_price_data(df)
                    success = True
                    success_count += 1
                    break
                if attempt < retry_times:
                    print(f"[Warning] {date_str} 無資料，{retry_delay} 秒後重試（第 {attempt}/{retry_times} 次）...")
                    time.sleep(retry_delay)
                else:
                    print(f"[Error] {date_str} 無法取得上櫃資料，已重試 {retry_times} 次")
            
            if not success:
                failed_dates.append(date_str)
            
            if idx < len(dates_to_update):
                time.sleep(self.polite_sleep)
        
        print("\n" + "=" * 60)
        print("批次取得上櫃資料完成")
        print("=" * 60)
        print(f"成功: {success_count} 天")
        print(f"失敗: {len(failed_dates)} 天")
        if failed_dates:
            print(f"失敗日期: {', '.join(failed_dates)}")
        
        return {
            'success': success_count,
            'failed': len(failed_dates),
            'skipped': days - len(dates_to_update),
            'total': days
        }

