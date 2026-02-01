"""
資料庫管理模組
連接資料庫，提供資料查詢和寫入功能
"""

import sqlite3
import pandas as pd
from datetime import datetime
import os


class DatabaseManager:
    """資料庫管理類別"""
    
    def __init__(self, db_path='D:\\all_data\\taiwan_stock_all_data.db'):
        """
        初始化資料庫管理器
        
        參數:
        - db_path: SQLite 資料庫路徑
        """
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """確保資料庫檔案存在"""
        if not os.path.exists(self.db_path):
            # 如果資料庫不存在，建立一個空資料庫
            conn = sqlite3.connect(self.db_path)
            conn.close()
            print(f"[Info] 建立新資料庫: {self.db_path}")
        
        # 確保所需資料表存在
        self.init_price_indices_table()
        self.init_return_indices_table()
        self.init_otc_stock_price_table()
        self.init_market_margin_table()
        # 確保上市/上櫃股票資料表含必要欄位
        self.ensure_table_column('tw_stock_price_data', 'odd_lot_filled', 'INTEGER DEFAULT 0')
        self.ensure_table_column('tw_otc_stock_price_data', 'odd_lot_filled', 'INTEGER DEFAULT 0')
        # 確保領先指標資料表含 M1B 年增率欄位
        self.ensure_table_column('leading_indicators_data', 'm1b_yoy_month', 'REAL')
        self.ensure_table_column('leading_indicators_data', 'm1b_yoy_momentum', 'REAL')
        self.ensure_table_column('leading_indicators_data', 'm1b_mom', 'REAL')
        self.ensure_table_column('leading_indicators_data', 'm1b_vs_3m_avg', 'REAL')
        # 初始化技術指標表
        self.init_stock_technical_indicators_table()
        self.init_stock_technical_indicators_monthly_table()
        # 初始化總經指標合併表
        self.init_merged_economic_indicators_table()
    
    def get_connection(self):
        """取得資料庫連接"""
        return sqlite3.connect(self.db_path)
    
    def execute_query(self, query, params=None):
        """
        執行查詢並回傳結果
        
        參數:
        - query: SQL 查詢語句
        - params: 查詢參數（可選）
        
        回傳:
        - 查詢結果列表
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            return results
        finally:
            conn.close()
    
    def execute_query_dataframe(self, query, params=None):
        """
        執行查詢並回傳 DataFrame
        
        參數:
        - query: SQL 查詢語句
        - params: 查詢參數（可選）
        
        回傳:
        - DataFrame
        """
        conn = self.get_connection()
        try:
            if params:
                df = pd.read_sql_query(query, conn, params=params)
            else:
                df = pd.read_sql_query(query, conn)
            return df
        finally:
            conn.close()
    
    def save_dataframe(self, df, table_name, if_exists='replace'):
        """
        儲存 DataFrame 到資料庫
        
        參數:
        - df: 要儲存的 DataFrame
        - table_name: 資料表名稱
        - if_exists: 如果表存在時的處理方式（'replace', 'append', 'fail'）
        """
        if df.empty:
            print(f"[Warning] DataFrame 為空，跳過儲存到 {table_name}")
            return
        
        conn = self.get_connection()
        try:
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
            print(f"[Info] 成功儲存 {len(df)} 筆資料到 {table_name}")
        except Exception as e:
            print(f"[Error] 儲存資料到 {table_name} 失敗: {e}")
            raise
        finally:
            conn.close()
    
    def get_stock_price(self, ticker=None, start_date=None, end_date=None):
        """
        取得股價資料
        
        參數:
        - ticker: 股票代號（None 表示所有股票）
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        
        回傳:
        - DataFrame
        """
        query = "SELECT * FROM tw_stock_price_data WHERE 1=1"
        params = []
        
        if ticker:
            query += " AND ticker = ?"
            params.append(str(ticker))
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date, ticker"
        
        return self.execute_query_dataframe(query, params if params else None)
    
    def get_otc_stock_price(self, ticker=None, start_date=None, end_date=None):
        """
        取得上櫃股價資料
        """
        query = "SELECT * FROM tw_otc_stock_price_data WHERE 1=1"
        params = []
        
        if ticker:
            query += " AND ticker = ?"
            params.append(str(ticker))
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date, ticker"
        
        return self.execute_query_dataframe(query, params if params else None)
    
    def get_trading_dates(self, start_date=None, end_date=None):
        """
        取得交易日列表
        
        參數:
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        
        回傳:
        - 交易日列表（字串格式 YYYYMMDD）
        """
        query = "SELECT DISTINCT date FROM tw_stock_price_data WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date"
        
        results = self.execute_query(query, params if params else None)
        return [row[0] for row in results]
    
    def check_table_exists(self, table_name):
        """
        檢查資料表是否存在
        
        參數:
        - table_name: 資料表名稱
        
        回傳:
        - True 或 False
        """
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        results = self.execute_query(query, (table_name,))
        return len(results) > 0
    
    def get_table_schema(self, table_name):
        """
        取得資料表結構
        
        參數:
        - table_name: 資料表名稱
        
        回傳:
        - 資料表結構資訊
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            return cursor.fetchall()
        finally:
            conn.close()
    
    def ensure_table_column(self, table_name, column_name, column_definition):
        """
        確保指定資料表包含特定欄位，若不存在則新增
        """
        if not self.check_table_exists(table_name):
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            if column_name in column_names:
                return
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )
            conn.commit()
            print(f"[Info] {table_name} 已新增欄位 {column_name}")
        except Exception as e:
            conn.rollback()
            print(f"[Warning] 無法為 {table_name} 新增欄位 {column_name}: {e}")
        finally:
            conn.close()
    
    def ensure_vix_data_derivative_columns(self):
        """
        確保 VIX_data 表存在且包含衍生指標欄位；若表不存在則不動作。
        衍生欄位：vix_change, vix_change_pct, vix_range, vix_range_pct, vix_mom,
                 vix_close_lag1, vix_close_lag2, vix_ma3, vix_ma6
        """
        if not self.check_table_exists('VIX_data'):
            return
        for col, definition in [
            ('vix_change', 'REAL'),
            ('vix_change_pct', 'REAL'),
            ('vix_range', 'REAL'),
            ('vix_range_pct', 'REAL'),
            ('vix_mom', 'REAL'),
            ('vix_close_lag1', 'REAL'),
            ('vix_close_lag2', 'REAL'),
            ('vix_ma3', 'REAL'),
            ('vix_ma6', 'REAL'),
        ]:
            self.ensure_table_column('VIX_data', col, definition)
    
    def get_vix_data(self, start_date=None, end_date=None):
        """
        取得 VIX_data 月 K 線（含衍生指標）。
        start_date / end_date 為 YYYYMMDD 或 YYYYMM，依 tradeDate 過濾。
        """
        if not self.check_table_exists('VIX_data'):
            return pd.DataFrame()
        s = str(start_date).strip() if start_date else None
        e = str(end_date).strip() if end_date else None
        if s and len(s) == 6:
            s = s + '01'
        if e and len(e) == 6:
            e = e + '31'
        query = "SELECT * FROM VIX_data WHERE 1=1"
        params = []
        if s:
            query += " AND tradeDate >= ?"
            params.append(s)
        if e:
            query += " AND tradeDate <= ?"
            params.append(e)
        query += " ORDER BY tradeDate"
        return self.execute_query_dataframe(query, params if params else None)
    
    def init_price_indices_table(self):
        """
        初始化價格指數資料表（tw_price_indices_data）
        根據 API 回應格式設計：指數名稱、收盤指數、漲跌符號、漲跌點數、漲跌百分比、特殊處理註記
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tw_price_indices_data'")
            table_exists = cursor.fetchone()
            
            if table_exists:
                # 檢查表結構是否正確（檢查是否有 close_index 欄位）
                cursor.execute("PRAGMA table_info(tw_price_indices_data)")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                # 如果表存在但結構不正確（沒有 close_index 欄位），需要重建表
                if 'close_index' not in column_names:
                    print("[Info] 偵測到舊版價格指數表結構，正在重建...")
                    # 刪除舊表
                    cursor.execute("DROP TABLE tw_price_indices_data")
                    conn.commit()
            
            # 建立價格指數資料表（符合 API 格式）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tw_price_indices_data (
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    close_index REAL,
                    change_sign TEXT,
                    change_points REAL,
                    change_pct REAL,
                    special_note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            
            conn.commit()
            print(f"[Info] 價格指數資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化價格指數資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_return_indices_table(self):
        """
        初始化報酬指數資料表（tw_return_indices_data）
        結構與價格指數表相同
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tw_return_indices_data'")
            table_exists = cursor.fetchone()
            
            if table_exists:
                # 檢查表結構是否正確（檢查是否有 close_index 欄位）
                cursor.execute("PRAGMA table_info(tw_return_indices_data)")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                # 如果表存在但結構不正確（沒有 close_index 欄位），需要重建表
                if 'close_index' not in column_names:
                    print("[Info] 偵測到舊版報酬指數表結構，正在重建...")
                    # 刪除舊表
                    cursor.execute("DROP TABLE tw_return_indices_data")
                    conn.commit()
            
            # 建立報酬指數資料表（符合 API 格式）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tw_return_indices_data (
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    close_index REAL,
                    change_sign TEXT,
                    change_points REAL,
                    change_pct REAL,
                    special_note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            
            conn.commit()
            print(f"[Info] 報酬指數資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化報酬指數資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_otc_stock_price_table(self):
        """
        初始化上櫃股票資料表（tw_otc_stock_price_data）
        結構與上市股票資料表相同，獨立儲存櫃買中心資料
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tw_otc_stock_price_data (
                    date TEXT NOT NULL,
                    stock_name TEXT,
                    ticker TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    turnover REAL,
                    change REAL,
                    odd_lot_filled INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            conn.commit()
            print("[Info] 上櫃股票資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化上櫃股票資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_market_margin_table(self):
        """
        初始化大盤融資融券資料表（market_margin_data）
        儲存從證交所 MI_MARGN API 取得的每日融資融券原始數據
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS market_margin_data (
                    date TEXT PRIMARY KEY,
                    -- 融資(交易單位) 相關欄位
                    margin_buy_units TEXT,
                    margin_sell_units TEXT,
                    margin_cash_repay_units TEXT,
                    margin_prev_balance_units TEXT,
                    margin_today_balance_units TEXT,
                    -- 融券(交易單位) 相關欄位
                    short_buy_units TEXT,
                    short_sell_units TEXT,
                    short_cash_repay_units TEXT,
                    short_prev_balance_units TEXT,
                    short_today_balance_units TEXT,
                    -- 融資金額(仟元) 相關欄位
                    margin_buy_amount TEXT,
                    margin_sell_amount TEXT,
                    margin_cash_repay_amount TEXT,
                    margin_prev_balance_amount TEXT,
                    margin_today_balance_amount TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("[Info] 大盤融資融券資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化大盤融資融券資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def get_market_margin_data(self, start_date=None, end_date=None):
        """
        取得大盤融資融券資料
        
        參數:
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        
        回傳:
        - DataFrame
        """
        query = "SELECT * FROM market_margin_data WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date"
        
        return self.execute_query_dataframe(query, params if params else None)
    
    def get_price_indices(self, ticker=None, start_date=None, end_date=None):
        """
        取得價格指數資料
        
        參數:
        - ticker: 指數名稱（None 表示所有指數）
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        
        回傳:
        - DataFrame
        """
        query = "SELECT * FROM tw_price_indices_data WHERE 1=1"
        params = []
        
        if ticker:
            query += " AND ticker = ?"
            params.append(str(ticker))
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date, ticker"
        
        return self.execute_query_dataframe(query, params if params else None)
    
    def clear_table_data(self, table_name):
        """
        清除指定表的資料
        
        參數:
        - table_name: 要清除的資料表名稱
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"DELETE FROM {table_name}")
            conn.commit()
            print(f"[Info] 已清除 {table_name} 表的所有資料")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 清除 {table_name} 表資料失敗: {e}")
            raise
        finally:
            conn.close()
    
    def modify_stock_price_table_add_stock_name(self):
        """
        修改 tw_stock_price_data 表，在 date 和 ticker 之間新增 stock_name 欄位
        由於 SQLite 不支援 ALTER TABLE ADD COLUMN AFTER，需要重建表結構
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tw_stock_price_data'")
            if not cursor.fetchone():
                print("[Info] tw_stock_price_data 表不存在，將建立新表")
                cursor.execute('''
                    CREATE TABLE tw_stock_price_data (
                        date TEXT NOT NULL,
                        stock_name TEXT,
                        ticker TEXT NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume INTEGER,
                        turnover REAL,
                        change REAL,
                        odd_lot_filled INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (date, ticker)
                    )
                ''')
                conn.commit()
                print("[Info] 已建立新的 tw_stock_price_data 表（包含 stock_name 欄位）")
                return
            
            # 檢查是否已有 stock_name 欄位
            cursor.execute("PRAGMA table_info(tw_stock_price_data)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'stock_name' in column_names:
                print("[Info] tw_stock_price_data 表已包含 stock_name 欄位，無需修改")
                return
            
            # 如果表存在但沒有 stock_name 欄位，需要重建表
            print("[Info] 開始重建 tw_stock_price_data 表結構...")
            
            # 建立新表（包含 stock_name 欄位）
            cursor.execute('''
                CREATE TABLE tw_stock_price_data_new (
                    date TEXT NOT NULL,
                    stock_name TEXT,
                    ticker TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    turnover REAL,
                    change REAL,
                    odd_lot_filled INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            
            # 複製舊資料到新表（stock_name 設為 NULL）
            cursor.execute('''
                INSERT INTO tw_stock_price_data_new 
                (date, stock_name, ticker, open, high, low, close, volume, turnover, change, odd_lot_filled, created_at)
                SELECT date, NULL as stock_name, ticker, open, high, low, close, volume, turnover, change, 0 as odd_lot_filled, created_at
                FROM tw_stock_price_data
            ''')
            
            # 刪除舊表
            cursor.execute("DROP TABLE tw_stock_price_data")
            
            # 重新命名新表
            cursor.execute("ALTER TABLE tw_stock_price_data_new RENAME TO tw_stock_price_data")
            
            conn.commit()
            print("[Info] tw_stock_price_data 表結構重建完成（已加入 stock_name 欄位）")
            
        except Exception as e:
            conn.rollback()
            print(f"[Error] 修改 tw_stock_price_data 表結構失敗: {e}")
            raise
        finally:
            conn.close()
    
    def get_return_indices(self, ticker=None, start_date=None, end_date=None):
        """
        取得報酬指數資料
        
        參數:
        - ticker: 指數代號（None 表示所有指數）
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        
        回傳:
        - DataFrame
        """
        query = "SELECT * FROM tw_return_indices_data WHERE 1=1"
        params = []
        
        if ticker:
            query += " AND ticker = ?"
            params.append(str(ticker))
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date, ticker"
        
        return self.execute_query_dataframe(query, params if params else None)
    
    def clear_table_data(self, table_name):
        """
        清除資料表的所有資料
        
        參數:
        - table_name: 資料表名稱
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"DELETE FROM {table_name}")
            conn.commit()
            print(f"[Info] 已清除 {table_name} 表的所有資料")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 清除 {table_name} 表資料失敗: {e}")
            raise
        finally:
            conn.close()
    
    def modify_stock_price_table_add_stock_name(self):
        """
        修改 tw_stock_price_data 表結構，在 date 和 ticker 之間加入 stock_name 欄位
        由於 SQLite 不支援 ALTER TABLE ADD COLUMN AFTER，需要重建表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查表是否存在
            if not self.check_table_exists('tw_stock_price_data'):
                print("[Info] tw_stock_price_data 表不存在，直接建立新表")
                cursor.execute('''
                    CREATE TABLE tw_stock_price_data (
                        date TEXT NOT NULL,
                        stock_name TEXT,
                        ticker TEXT NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume INTEGER,
                        turnover REAL,
                        change REAL,
                        odd_lot_filled INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (date, ticker)
                    )
                ''')
                conn.commit()
                print("[Info] 已建立包含 stock_name 欄位的 tw_stock_price_data 表")
                return
            
            # 檢查是否已有 stock_name 欄位
            schema = self.get_table_schema('tw_stock_price_data')
            column_names = [col[1] for col in schema]
            
            if 'stock_name' in column_names:
                print("[Info] tw_stock_price_data 表已包含 stock_name 欄位，無需修改")
                return
            
            print("[Info] 開始重建 tw_stock_price_data 表結構...")
            
            # 1. 建立新表（包含 stock_name 欄位）
            cursor.execute('''
                CREATE TABLE tw_stock_price_data_new (
                    date TEXT NOT NULL,
                    stock_name TEXT,
                    ticker TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    turnover REAL,
                    change REAL,
                    odd_lot_filled INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            
            # 2. 複製舊資料（stock_name 設為 NULL）
            cursor.execute('''
                INSERT INTO tw_stock_price_data_new 
                (date, ticker, open, high, low, close, volume, turnover, change, odd_lot_filled, created_at)
                SELECT date, ticker, open, high, low, close, volume, turnover, change, 0 as odd_lot_filled, created_at
                FROM tw_stock_price_data
            ''')
            
            # 3. 刪除舊表
            cursor.execute('DROP TABLE tw_stock_price_data')
            
            # 4. 重新命名新表
            cursor.execute('ALTER TABLE tw_stock_price_data_new RENAME TO tw_stock_price_data')
            
            conn.commit()
            print("[Info] 已成功重建 tw_stock_price_data 表結構，加入 stock_name 欄位")
            
        except Exception as e:
            conn.rollback()
            print(f"[Error] 修改 tw_stock_price_data 表結構失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_leading_indicators_table(self):
        """
        初始化領先指標資料表（leading_indicators_data）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leading_indicators_data (
                    date TEXT NOT NULL PRIMARY KEY,
                    export_order_index REAL,
                    m1b_money_supply REAL,
                    m1b_yoy_month REAL,
                    m1b_yoy_momentum REAL,
                    m1b_mom REAL,
                    m1b_vs_3m_avg REAL,
                    stock_price_index REAL,
                    employment_net_entry_rate REAL,
                    building_floor_area REAL,
                    semiconductor_import REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("[Info] 領先指標資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化領先指標資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_coincident_indicators_table(self):
        """
        初始化同時指標資料表（coincident_indicators_data）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS coincident_indicators_data (
                    date TEXT NOT NULL PRIMARY KEY,
                    industrial_production_index REAL,
                    electricity_consumption REAL,
                    manufacturing_sales_index REAL,
                    wholesale_retail_revenue REAL,
                    overtime_hours REAL,
                    export_value REAL,
                    machinery_import REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("[Info] 同時指標資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化同時指標資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_lagging_indicators_table(self):
        """
        初始化落後指標資料表（lagging_indicators_data）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS lagging_indicators_data (
                    date TEXT NOT NULL PRIMARY KEY,
                    unemployment_rate REAL,
                    labor_cost_index REAL,
                    loan_interest_rate REAL,
                    financial_institution_loans REAL,
                    manufacturing_inventory REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("[Info] 落後指標資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化落後指標資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_composite_indicators_table(self):
        """
        初始化綜合指標資料表（composite_indicators_data）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS composite_indicators_data (
                    date TEXT NOT NULL PRIMARY KEY,
                    leading_index REAL,
                    leading_index_no_trend REAL,
                    coincident_index REAL,
                    coincident_index_no_trend REAL,
                    lagging_index REAL,
                    lagging_index_no_trend REAL,
                    business_cycle_score REAL,
                    business_cycle_signal TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("[Info] 綜合指標資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化綜合指標資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_business_cycle_signal_components_table(self):
        """
        初始化景氣對策信號構成項目資料表（business_cycle_signal_components_data）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS business_cycle_signal_components_data (
                    date TEXT NOT NULL PRIMARY KEY,
                    m1b_money_supply REAL,
                    stock_price_index REAL,
                    industrial_production_index REAL,
                    overtime_hours REAL,
                    export_value REAL,
                    machinery_import REAL,
                    manufacturing_sales_index REAL,
                    wholesale_retail_revenue REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("[Info] 景氣對策信號構成項目資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化景氣對策信號構成項目資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_all_indicator_tables(self):
        """
        初始化所有景氣指標資料表
        """
        self.init_leading_indicators_table()
        self.init_coincident_indicators_table()
        self.init_lagging_indicators_table()
        self.init_composite_indicators_table()
        self.init_business_cycle_signal_components_table()
        self.init_merged_economic_indicators_table()
        print("[Info] 所有景氣指標資料表初始化完成")
    
    def init_merged_economic_indicators_table(self):
        """
        初始化總經指標合併表（merged_economic_indicators）
        此表包含所有合併後的總經指標，帶前綴（leading_, coincident_, lagging_, signal_）
        注意：表結構會動態調整以適應實際匯入的欄位
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='merged_economic_indicators'")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                # 建立基本表結構（只包含日期欄位）
                # 其他欄位會在 calculate_and_save_merged_indicators 中動態添加
                cursor.execute('''
                    CREATE TABLE merged_economic_indicators (
                        indicator_date TEXT NOT NULL PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                print("[Info] 總經指標合併表初始化完成（基本結構）")
            else:
                print("[Info] 總經指標合併表已存在")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化總經指標合併表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_stock_technical_indicators_table(self):
        """
        初始化日線技術指標資料表（stock_technical_indicators）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_technical_indicators (
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    ma5 REAL,
                    ma20 REAL,
                    ma60 REAL,
                    price_vs_ma5 REAL,
                    price_vs_ma20 REAL,
                    volatility_20 REAL,
                    volatility_pct_20 REAL,
                    return_1d REAL,
                    return_5d REAL,
                    return_20d REAL,
                    rsi REAL,
                    volume_ma5 REAL,
                    volume_ratio REAL,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            conn.commit()
            print("[Info] 日線技術指標資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化日線技術指標資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_stock_technical_indicators_monthly_table(self):
        """
        初始化月線技術指標資料表（stock_technical_indicators_monthly）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_technical_indicators_monthly (
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    ma3 REAL,
                    ma6 REAL,
                    ma12 REAL,
                    price_vs_ma3 REAL,
                    price_vs_ma6 REAL,
                    volatility_6 REAL,
                    volatility_pct_6 REAL,
                    return_1m REAL,
                    return_3m REAL,
                    return_12m REAL,
                    rsi REAL,
                    volume_ma3 REAL,
                    volume_ratio REAL,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            conn.commit()
            print("[Info] 月線技術指標資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化月線技術指標資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def ensure_etf_006208_monthly_future_table(self):
        """
        確保 etf_006208_monthly_future 資料表存在。
        儲存 006208 月線 OHLCV、月均價/月中位數、三種未來1月報酬率、未來1月最高/最低價。
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS etf_006208_monthly_future (
                    date TEXT NOT NULL PRIMARY KEY,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    turnover REAL,
                    close_avg_month REAL,
                    close_median_month REAL,
                    future_return_1m REAL,
                    future_return_1m_avg REAL,
                    future_return_1m_median REAL,
                    future_high_1m REAL,
                    future_low_1m REAL
                )
            ''')
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[Error] ensure_etf_006208_monthly_future_table 失敗: {e}")
            raise
        finally:
            conn.close()
    
    def create_chinese_views(self):
        """
        為所有資料表建立中文別名 VIEW
        使用 vw_ 前綴命名，例如：vw_tw_stock_price_data
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            print("\n[Info] 開始建立中文別名 VIEW...")
            
            # 檢查所有資料表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            # 1. vw_tw_stock_price_data - 上市股票和ETF股價資料
            cursor.execute("DROP VIEW IF EXISTS vw_tw_stock_price_data")
            cursor.execute('''
                CREATE VIEW vw_tw_stock_price_data AS
                SELECT 
                    date AS '日期',
                    stock_name AS '股票名稱',
                    ticker AS '股票代號',
                    open AS '開盤價',
                    high AS '最高價',
                    low AS '最低價',
                    close AS '收盤價',
                    volume AS '成交量(股數)',
                    turnover AS '成交金額(元)',
                    change AS '漲跌價差',
                    odd_lot_filled AS '零股填補標記',
                    created_at AS '資料建立時間'
                FROM tw_stock_price_data
            ''')
            print("[Info] 已建立: vw_tw_stock_price_data")
            
            # 2. vw_tw_otc_stock_price_data - 上櫃股票股價資料
            cursor.execute("DROP VIEW IF EXISTS vw_tw_otc_stock_price_data")
            cursor.execute('''
                CREATE VIEW vw_tw_otc_stock_price_data AS
                SELECT 
                    date AS '日期',
                    stock_name AS '股票名稱',
                    ticker AS '股票代號',
                    open AS '開盤價',
                    high AS '最高價',
                    low AS '最低價',
                    close AS '收盤價',
                    volume AS '成交量(股數)',
                    turnover AS '成交金額(元)',
                    change AS '漲跌價差',
                    odd_lot_filled AS '零股填補標記',
                    created_at AS '資料建立時間'
                FROM tw_otc_stock_price_data
            ''')
            print("[Info] 已建立: vw_tw_otc_stock_price_data")
            
            # 3. vw_tw_price_indices_data - 價格指數資料
            cursor.execute("DROP VIEW IF EXISTS vw_tw_price_indices_data")
            cursor.execute('''
                CREATE VIEW vw_tw_price_indices_data AS
                SELECT 
                    date AS '日期',
                    ticker AS '指數代號',
                    close_index AS '收盤指數',
                    change_sign AS '漲跌符號',
                    change_points AS '漲跌點數',
                    change_pct AS '漲跌百分比',
                    special_note AS '特殊註記',
                    created_at AS '資料建立時間'
                FROM tw_price_indices_data
            ''')
            print("[Info] 已建立: vw_tw_price_indices_data")
            
            # 4. vw_tw_return_indices_data - 報酬指數資料
            cursor.execute("DROP VIEW IF EXISTS vw_tw_return_indices_data")
            cursor.execute('''
                CREATE VIEW vw_tw_return_indices_data AS
                SELECT 
                    date AS '日期',
                    ticker AS '指數代號',
                    close_index AS '收盤指數',
                    change_sign AS '漲跌符號',
                    change_points AS '漲跌點數',
                    change_pct AS '漲跌百分比',
                    special_note AS '特殊註記',
                    created_at AS '資料建立時間'
                FROM tw_return_indices_data
            ''')
            print("[Info] 已建立: vw_tw_return_indices_data")
            
            # 5. vw_business_cycle_data - 景氣燈號資料
            cursor.execute("DROP VIEW IF EXISTS vw_business_cycle_data")
            try:
                cursor.execute('''
                    CREATE VIEW vw_business_cycle_data AS
                    SELECT 
                        date AS '日期',
                        score AS '景氣對策信號綜合分數',
                        val_shifted AS '前一日數值',
                        signal AS '景氣對策信號(燈號顏色)'
                    FROM business_cycle_data
                ''')
                print("[Info] 已建立: vw_business_cycle_data")
            except Exception as e:
                print(f"[Warning] 建立 vw_business_cycle_data 失敗: {e}")
                raise
            
            # 6. vw_leading_indicators_data - 領先指標構成項目
            cursor.execute("DROP VIEW IF EXISTS vw_leading_indicators_data")
            try:
                # 檢查 created_at 欄位是否存在
                cursor.execute("PRAGMA table_info(leading_indicators_data)")
                columns = [col[1] for col in cursor.fetchall()]
                has_created_at = 'created_at' in columns
                
                if has_created_at:
                    view_sql = '''
                        CREATE VIEW vw_leading_indicators_data AS
                        SELECT 
                            date AS '日期',
                            export_order_index AS '外銷訂單動向指數(以家數計)',
                            m1b_money_supply AS '貨幣總計數M1B(百萬元)',
                            m1b_yoy_month AS 'M1B月對月年增率(%)',
                            m1b_yoy_momentum AS 'M1B年增率動能(%)',
                            m1b_mom AS 'M1B月對月變化率(%)',
                            m1b_vs_3m_avg AS 'M1B當月vs前三個月平均變化率(%)',
                            stock_price_index AS '股價指數(Index1966=100)',
                            employment_net_entry_rate AS '工業及服務業受僱員工淨進入率(%)',
                            building_floor_area AS '建築物開工樓地板面積(千平方公尺)',
                            semiconductor_import AS '名目半導體設備進口(新臺幣百萬元)',
                            created_at AS '資料建立時間'
                        FROM leading_indicators_data
                    '''
                else:
                    view_sql = '''
                        CREATE VIEW vw_leading_indicators_data AS
                        SELECT 
                            date AS '日期',
                            export_order_index AS '外銷訂單動向指數(以家數計)',
                            m1b_money_supply AS '貨幣總計數M1B(百萬元)',
                            m1b_yoy_month AS 'M1B月對月年增率(%)',
                            m1b_yoy_momentum AS 'M1B年增率動能(%)',
                            m1b_mom AS 'M1B月對月變化率(%)',
                            m1b_vs_3m_avg AS 'M1B當月vs前三個月平均變化率(%)',
                            stock_price_index AS '股價指數(Index1966=100)',
                            employment_net_entry_rate AS '工業及服務業受僱員工淨進入率(%)',
                            building_floor_area AS '建築物開工樓地板面積(千平方公尺)',
                            semiconductor_import AS '名目半導體設備進口(新臺幣百萬元)'
                        FROM leading_indicators_data
                    '''
                
                cursor.execute(view_sql)
                print("[Info] 已建立: vw_leading_indicators_data")
            except Exception as e:
                print(f"[Warning] 建立 vw_leading_indicators_data 失敗: {e}")
                raise
            
            # 7. vw_coincident_indicators_data - 同時指標構成項目
            cursor.execute("DROP VIEW IF EXISTS vw_coincident_indicators_data")
            cursor.execute("PRAGMA table_info(coincident_indicators_data)")
            columns = [col[1] for col in cursor.fetchall()]
            has_created_at = 'created_at' in columns
            if has_created_at:
                cursor.execute('''
                    CREATE VIEW vw_coincident_indicators_data AS
                    SELECT 
                        date AS '日期',
                        industrial_production_index AS '工業生產指數(Index2021=100)',
                        electricity_consumption AS '電力(企業)總用電量(十億度)',
                        manufacturing_sales_index AS '製造業銷售量指數(Index2021=100)',
                        wholesale_retail_revenue AS '批發零售及餐飲業營業額(十億元)',
                        overtime_hours AS '工業及服務業加班工時(小時)',
                        export_value AS '海關出口值(十億元)',
                        machinery_import AS '機械及電機設備進口值(十億元)',
                        created_at AS '資料建立時間'
                    FROM coincident_indicators_data
                ''')
            else:
                cursor.execute('''
                    CREATE VIEW vw_coincident_indicators_data AS
                    SELECT 
                        date AS '日期',
                        industrial_production_index AS '工業生產指數(Index2021=100)',
                        electricity_consumption AS '電力(企業)總用電量(十億度)',
                        manufacturing_sales_index AS '製造業銷售量指數(Index2021=100)',
                        wholesale_retail_revenue AS '批發零售及餐飲業營業額(十億元)',
                        overtime_hours AS '工業及服務業加班工時(小時)',
                        export_value AS '海關出口值(十億元)',
                        machinery_import AS '機械及電機設備進口值(十億元)'
                    FROM coincident_indicators_data
                ''')
            print("[Info] 已建立: vw_coincident_indicators_data")
            
            # 8. vw_lagging_indicators_data - 落後指標構成項目
            cursor.execute("DROP VIEW IF EXISTS vw_lagging_indicators_data")
            cursor.execute("PRAGMA table_info(lagging_indicators_data)")
            columns = [col[1] for col in cursor.fetchall()]
            has_created_at = 'created_at' in columns
            if has_created_at:
                cursor.execute('''
                    CREATE VIEW vw_lagging_indicators_data AS
                    SELECT 
                        date AS '日期',
                        unemployment_rate AS '失業率(%)',
                        labor_cost_index AS '製造業單位產出勞動成本指數(2021=100)',
                        loan_interest_rate AS '五大銀行新承做放款平均利率(年息百分比)',
                        financial_institution_loans AS '全體金融機構放款與投資(10億元)',
                        manufacturing_inventory AS '製造業存貨價值(千元)',
                        created_at AS '資料建立時間'
                    FROM lagging_indicators_data
                ''')
            else:
                cursor.execute('''
                    CREATE VIEW vw_lagging_indicators_data AS
                    SELECT 
                        date AS '日期',
                        unemployment_rate AS '失業率(%)',
                        labor_cost_index AS '製造業單位產出勞動成本指數(2021=100)',
                        loan_interest_rate AS '五大銀行新承做放款平均利率(年息百分比)',
                        financial_institution_loans AS '全體金融機構放款與投資(10億元)',
                        manufacturing_inventory AS '製造業存貨價值(千元)'
                    FROM lagging_indicators_data
                ''')
            print("[Info] 已建立: vw_lagging_indicators_data")
            
            # 9. vw_composite_indicators_data - 景氣指標與燈號（綜合指標），領先→同時→落後順序含衍伸
            COMPOSITE_INDICATORS_CN_MAP = {
                'date': '日期',
                'leading_index': '領先指標綜合指數',
                'leading_index_mom': '領先指標綜合指數月對月變化',
                'leading_index_pct': '領先指標綜合指數變化率(%)',
                'leading_index_lag1': '領先指標綜合指數前1期',
                'leading_index_lag2': '領先指標綜合指數前2期',
                'leading_index_ma3': '領先指標綜合指數3月均',
                'leading_index_ma6': '領先指標綜合指數6月均',
                'leading_index_no_trend': '領先指標不含趨勢指數',
                'leading_index_no_trend_mom': '領先指標不含趨勢指數月對月變化',
                'leading_index_no_trend_pct': '領先指標不含趨勢指數變化率(%)',
                'leading_index_no_trend_lag1': '領先指標不含趨勢指數前1期',
                'leading_index_no_trend_lag2': '領先指標不含趨勢指數前2期',
                'leading_index_no_trend_ma3': '領先指標不含趨勢指數3月均',
                'leading_index_no_trend_ma6': '領先指標不含趨勢指數6月均',
                'coincident_index': '同時指標綜合指數',
                'coincident_index_mom': '同時指標綜合指數月對月變化',
                'coincident_index_pct': '同時指標綜合指數變化率(%)',
                'coincident_index_lag1': '同時指標綜合指數前1期',
                'coincident_index_lag2': '同時指標綜合指數前2期',
                'coincident_index_ma3': '同時指標綜合指數3月均',
                'coincident_index_ma6': '同時指標綜合指數6月均',
                'coincident_index_no_trend': '同時指標不含趨勢指數',
                'coincident_index_no_trend_mom': '同時指標不含趨勢指數月對月變化',
                'coincident_index_no_trend_pct': '同時指標不含趨勢指數變化率(%)',
                'coincident_index_no_trend_lag1': '同時指標不含趨勢指數前1期',
                'coincident_index_no_trend_lag2': '同時指標不含趨勢指數前2期',
                'coincident_index_no_trend_ma3': '同時指標不含趨勢指數3月均',
                'coincident_index_no_trend_ma6': '同時指標不含趨勢指數6月均',
                'lagging_index': '落後指標綜合指數',
                'lagging_index_mom': '落後指標綜合指數月對月變化',
                'lagging_index_pct': '落後指標綜合指數變化率(%)',
                'lagging_index_lag1': '落後指標綜合指數前1期',
                'lagging_index_lag2': '落後指標綜合指數前2期',
                'lagging_index_ma3': '落後指標綜合指數3月均',
                'lagging_index_ma6': '落後指標綜合指數6月均',
                'lagging_index_no_trend': '落後指標不含趨勢指數',
                'lagging_index_no_trend_mom': '落後指標不含趨勢指數月對月變化',
                'lagging_index_no_trend_pct': '落後指標不含趨勢指數變化率(%)',
                'lagging_index_no_trend_lag1': '落後指標不含趨勢指數前1期',
                'lagging_index_no_trend_lag2': '落後指標不含趨勢指數前2期',
                'lagging_index_no_trend_ma3': '落後指標不含趨勢指數3月均',
                'lagging_index_no_trend_ma6': '落後指標不含趨勢指數6月均',
                'business_cycle_score': '景氣對策信號綜合分數',
                'business_cycle_signal': '景氣對策信號(燈號顏色)',
                'created_at': '資料建立時間',
            }
            cursor.execute("DROP VIEW IF EXISTS vw_composite_indicators_data")
            cursor.execute("PRAGMA table_info(composite_indicators_data)")
            composite_columns = [col[1] for col in cursor.fetchall()]
            composite_order = (
                ['date']
                + [c for c in ['leading_index', 'leading_index_mom', 'leading_index_pct', 'leading_index_lag1', 'leading_index_lag2', 'leading_index_ma3', 'leading_index_ma6',
                              'leading_index_no_trend', 'leading_index_no_trend_mom', 'leading_index_no_trend_pct', 'leading_index_no_trend_lag1', 'leading_index_no_trend_lag2', 'leading_index_no_trend_ma3', 'leading_index_no_trend_ma6'] if c in composite_columns]
                + [c for c in ['coincident_index', 'coincident_index_mom', 'coincident_index_pct', 'coincident_index_lag1', 'coincident_index_lag2', 'coincident_index_ma3', 'coincident_index_ma6',
                              'coincident_index_no_trend', 'coincident_index_no_trend_mom', 'coincident_index_no_trend_pct', 'coincident_index_no_trend_lag1', 'coincident_index_no_trend_lag2', 'coincident_index_no_trend_ma3', 'coincident_index_no_trend_ma6'] if c in composite_columns]
                + [c for c in ['lagging_index', 'lagging_index_mom', 'lagging_index_pct', 'lagging_index_lag1', 'lagging_index_lag2', 'lagging_index_ma3', 'lagging_index_ma6',
                              'lagging_index_no_trend', 'lagging_index_no_trend_mom', 'lagging_index_no_trend_pct', 'lagging_index_no_trend_lag1', 'lagging_index_no_trend_lag2', 'lagging_index_no_trend_ma3', 'lagging_index_no_trend_ma6'] if c in composite_columns]
                + [c for c in ['business_cycle_score', 'business_cycle_signal', 'created_at'] if c in composite_columns]
            )
            composite_select = [f"{c} AS '{COMPOSITE_INDICATORS_CN_MAP[c]}'" for c in composite_order if c in COMPOSITE_INDICATORS_CN_MAP]
            view_sql = f"CREATE VIEW vw_composite_indicators_data AS SELECT {', '.join(composite_select)} FROM composite_indicators_data"
            cursor.execute(view_sql)
            print("[Info] 已建立: vw_composite_indicators_data")
            
            # 10. vw_business_cycle_signal_components_data - 景氣對策信號構成項目
            cursor.execute("DROP VIEW IF EXISTS vw_business_cycle_signal_components_data")
            cursor.execute("PRAGMA table_info(business_cycle_signal_components_data)")
            columns = [col[1] for col in cursor.fetchall()]
            has_created_at = 'created_at' in columns
            has_m1b_yoy_month = 'm1b_yoy_month' in columns
            has_m1b_yoy_rolling_12m = 'm1b_yoy_rolling_12m' in columns
            
            # 根據實際存在的欄位動態建立 VIEW
            select_fields = ["date AS '日期'"]
            if 'm1b_money_supply' in columns:
                select_fields.append("m1b_money_supply AS '貨幣總計數M1B(百萬元)'")
            if has_m1b_yoy_month:
                select_fields.append("m1b_yoy_month AS 'M1B月對月年增率(%)'")
            if has_m1b_yoy_rolling_12m:
                select_fields.append("m1b_yoy_rolling_12m AS 'M1B滾動12個月年增率(%)'")
            if 'stock_price_index' in columns:
                select_fields.append("stock_price_index AS '股價指數(Index1966=100)'")
            if 'industrial_production_index' in columns:
                select_fields.append("industrial_production_index AS '工業生產指數(Index2021=100)'")
            if 'overtime_hours' in columns:
                select_fields.append("overtime_hours AS '工業及服務業加班工時(小時)'")
            if 'export_value' in columns:
                select_fields.append("export_value AS '海關出口值(十億元)'")
            if 'machinery_import' in columns:
                select_fields.append("machinery_import AS '機械及電機設備進口值(十億元)'")
            if 'manufacturing_sales_index' in columns:
                select_fields.append("manufacturing_sales_index AS '製造業銷售量指數(Index2021=100)'")
            if 'wholesale_retail_revenue' in columns:
                select_fields.append("wholesale_retail_revenue AS '批發零售及餐飲業營業額(十億元)'")
            if has_created_at:
                select_fields.append("created_at AS '資料建立時間'")
            
            view_sql = f'''
                CREATE VIEW vw_business_cycle_signal_components_data AS
                SELECT 
                    {', '.join(select_fields)}
                FROM business_cycle_signal_components_data
            '''
            
            cursor.execute(view_sql)
            print("[Info] 已建立: vw_business_cycle_signal_components_data")
            
            # 11. vw_market_margin_data - 大盤融資融券資料
            cursor.execute("DROP VIEW IF EXISTS vw_market_margin_data")
            cursor.execute('''
                CREATE VIEW vw_market_margin_data AS
                SELECT 
                    date AS '日期',
                    margin_buy_units AS '融資買進(交易單位)',
                    margin_sell_units AS '融資賣出(交易單位)',
                    margin_cash_repay_units AS '融資現金券償還(交易單位)',
                    margin_prev_balance_units AS '融資前日餘額(交易單位)',
                    margin_today_balance_units AS '融資今日餘額(交易單位)',
                    short_buy_units AS '融券買進(交易單位)',
                    short_sell_units AS '融券賣出(交易單位)',
                    short_cash_repay_units AS '融券現金券償還(交易單位)',
                    short_prev_balance_units AS '融券前日餘額(交易單位)',
                    short_today_balance_units AS '融券今日餘額(交易單位)',
                    margin_buy_amount AS '融資買進(仟元)',
                    margin_sell_amount AS '融資賣出(仟元)',
                    margin_cash_repay_amount AS '融資現金券償還(仟元)',
                    margin_prev_balance_amount AS '融資前日餘額(仟元)',
                    margin_today_balance_amount AS '融資今日餘額(仟元)',
                    short_margin_ratio AS '券資比',
                    margin_balance_change_rate AS '融資餘額變化率',
                    margin_balance_net_change AS '融資餘額淨增減(仟元)',
                    margin_buy_sell_ratio AS '融資買賣比',
                    margin_buy_sell_net AS '融資買賣淨額(仟元)',
                    short_balance_change_rate AS '融券餘額變化率',
                    short_balance_net_change AS '融券餘額淨增減(交易單位)',
                    short_buy_sell_ratio AS '融券買賣比',
                    short_buy_sell_net AS '融券買賣淨額(交易單位)',
                    created_at AS '資料建立時間'
                FROM market_margin_data
            ''')
            print("[Info] 已建立: vw_market_margin_data")
            
            # 12. vw_TFE_VIX_data - VIX 原始資料
            cursor.execute("DROP VIEW IF EXISTS vw_TFE_VIX_data")
            cursor.execute('''
                CREATE VIEW vw_TFE_VIX_data AS
                SELECT 
                    date AS '日期',
                    time AS '時間',
                    vix AS 'VIX指數'
                FROM TFE_VIX_data
            ''')
            print("[Info] 已建立: vw_TFE_VIX_data")
            
            # 13. vw_VIX_data - VIX 月K線資料
            cursor.execute("DROP VIEW IF EXISTS vw_VIX_data")
            cursor.execute('''
                CREATE VIEW vw_VIX_data AS
                SELECT 
                    time AS '時間',
                    tradeDate AS '交易日期',
                    open AS '開盤',
                    high AS '最高',
                    low AS '最低',
                    close AS '收盤',
                    volume AS '成交量',
                    millionAmount AS '成交金額(百萬元)'
                FROM VIX_data
            ''')
            print("[Info] 已建立: vw_VIX_data")
            
            # 14. vw_stock_technical_indicators - 日線技術指標
            cursor.execute("DROP VIEW IF EXISTS vw_stock_technical_indicators")
            try:
                cursor.execute('''
                    CREATE VIEW vw_stock_technical_indicators AS
                    SELECT 
                        date AS '日期',
                        ticker AS '股票代號',
                        ma5 AS '5日移動平均線',
                        ma20 AS '20日移動平均線',
                        ma60 AS '60日移動平均線',
                        price_vs_ma5 AS '股價相對5日均線位置(%)',
                        price_vs_ma20 AS '股價相對20日均線位置(%)',
                        volatility_20 AS '20日波動率',
                        volatility_pct_20 AS '20日波動率(%)',
                        return_1d AS '1日報酬率(%)',
                        return_5d AS '5日報酬率(%)',
                        return_20d AS '20日報酬率(%)',
                        rsi AS 'RSI指標(14日)',
                        volume_ma5 AS '5日平均成交量',
                        volume_ratio AS '成交量比率'
                    FROM stock_technical_indicators
                ''')
                print("[Info] 已建立: vw_stock_technical_indicators")
            except Exception as e:
                print(f"[Warning] 建立 vw_stock_technical_indicators 失敗: {e}")
            
            # 15. vw_stock_technical_indicators_monthly - 月線技術指標
            cursor.execute("DROP VIEW IF EXISTS vw_stock_technical_indicators_monthly")
            try:
                cursor.execute('''
                    CREATE VIEW vw_stock_technical_indicators_monthly AS
                    SELECT 
                        date AS '日期（月末）',
                        ticker AS '股票代號',
                        ma3 AS '3月移動平均線',
                        ma6 AS '6月移動平均線',
                        ma12 AS '12月移動平均線',
                        price_vs_ma3 AS '股價相對3月均線位置(%)',
                        price_vs_ma6 AS '股價相對6月均線位置(%)',
                        volatility_6 AS '6月波動率',
                        volatility_pct_6 AS '6月波動率(%)',
                        return_1m AS '1月報酬率(%)',
                        return_3m AS '3月報酬率(%)',
                        return_12m AS '12月報酬率(%)',
                        rsi AS 'RSI指標(6月)',
                        volume_ma3 AS '3月平均成交量',
                        volume_ratio AS '成交量比率'
                    FROM stock_technical_indicators_monthly
                ''')
                print("[Info] 已建立: vw_stock_technical_indicators_monthly")
            except Exception as e:
                print(f"[Warning] 建立 vw_stock_technical_indicators_monthly 失敗: {e}")
            
            # 16. vw_merged_economic_indicators - 總經指標合併表
            cursor.execute("DROP VIEW IF EXISTS vw_merged_economic_indicators")
            try:
                # 檢查表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='merged_economic_indicators'")
                if not cursor.fetchone():
                    print("[Warning] merged_economic_indicators 表不存在，跳過建立 VIEW")
                else:
                    # 取得表結構
                    cursor.execute("PRAGMA table_info(merged_economic_indicators)")
                    columns = cursor.fetchall()
                    column_names = [col[1] for col in columns]
                    
                    if 'indicator_date' not in column_names:
                        print("[Warning] merged_economic_indicators 表缺少 indicator_date 欄位")
                    else:
                        # 建立欄位映射字典
                        column_mapping = {
                            'indicator_date': '日期',
                            'created_at': '資料建立時間'
                        }
                        
                        # 領先指標映射
                        leading_mapping = {
                            'leading_export_order_index': '領先_外銷訂單動向指數(以家數計)',
                            'leading_m1b_money_supply': '領先_貨幣總計數M1B(百萬元)',
                            'leading_m1b_yoy_month': '領先_M1B月對月年增率(%)',
                            'leading_m1b_yoy_momentum': '領先_M1B年增率動能(%)',
                            'leading_m1b_mom': '領先_M1B月對月變化率(%)',
                            'leading_m1b_vs_3m_avg': '領先_M1B當月vs前三個月平均變化率(%)',
                            'leading_stock_price_index': '領先_股價指數(Index1966=100)',
                            'leading_employment_net_entry_rate': '領先_工業及服務業受僱員工淨進入率(%)',
                            'leading_building_floor_area': '領先_建築物開工樓地板面積(千平方公尺)',
                            'leading_semiconductor_import': '領先_名目半導體設備進口(新臺幣百萬元)'
                        }
                        
                        # 同時指標映射
                        coincident_mapping = {
                            'coincident_industrial_production_index': '同時_工業生產指數(Index2021=100)',
                            'coincident_electricity_consumption': '同時_電力(企業)總用電量(十億度)',
                            'coincident_manufacturing_sales_index': '同時_製造業銷售量指數(Index2021=100)',
                            'coincident_wholesale_retail_revenue': '同時_批發零售及餐飲業營業額(十億元)',
                            'coincident_overtime_hours': '同時_工業及服務業加班工時(小時)',
                            'coincident_export_value': '同時_海關出口值(十億元)',
                            'coincident_machinery_import': '同時_機械及電機設備進口值(十億元)'
                        }
                        
                        # 落後指標映射
                        lagging_mapping = {
                            'lagging_unemployment_rate': '落後_失業率(%)',
                            'lagging_labor_cost_index': '落後_製造業單位產出勞動成本指數(2021=100)',
                            'lagging_loan_interest_rate': '落後_五大銀行新承做放款平均利率(年息百分比)',
                            'lagging_financial_institution_loans': '落後_全體金融機構放款與投資(10億元)',
                            'lagging_manufacturing_inventory': '落後_製造業存貨價值(千元)'
                        }
                        
                        # 信號指標映射
                        signal_mapping = {
                            'signal_leading_index': '信號_領先指標綜合指數',
                            'signal_leading_index_no_trend': '信號_領先指標不含趨勢指數',
                            'signal_coincident_index': '信號_同時指標綜合指數',
                            'signal_coincident_index_no_trend': '信號_同時指標不含趨勢指數',
                            'signal_lagging_index': '信號_落後指標綜合指數',
                            'signal_lagging_index_no_trend': '信號_落後指標不含趨勢指數',
                            'signal_business_cycle_score': '信號_景氣對策信號綜合分數',
                            'signal_business_cycle_signal': '信號_景氣對策信號(燈號顏色)'
                        }
                        
                        # 合併所有映射
                        column_mapping.update(leading_mapping)
                        column_mapping.update(coincident_mapping)
                        column_mapping.update(lagging_mapping)
                        column_mapping.update(signal_mapping)
                        
                        # 建立 SELECT 語句
                        select_fields = []
                        for col_name in column_names:
                            if col_name in column_mapping:
                                select_fields.append(f"{col_name} AS '{column_mapping[col_name]}'")
                            else:
                                # 如果沒有映射，使用原欄位名稱
                                select_fields.append(col_name)
                        
                        view_sql = f'''
                            CREATE VIEW vw_merged_economic_indicators AS
                            SELECT 
                                {', '.join(select_fields)}
                            FROM merged_economic_indicators
                        '''
                        
                        cursor.execute(view_sql)
                        print("[Info] 已建立: vw_merged_economic_indicators")
            except Exception as e:
                print(f"[Warning] 建立 vw_merged_economic_indicators 失敗: {e}")
            
            conn.commit()
            
            # 檢查所有原始資料表的資料筆數
            print(f"\n[Info] 原始資料表資料筆數統計：")
            for table_name in existing_tables:
                if table_name not in ['strategy_result', 'twse_margin_data']:  # 跳過不需要建立 VIEW 的表
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        table_count = cursor.fetchone()[0]
                        if table_count == 0:
                            print(f"  ⚠ {table_name}: {table_count} 筆（空的）")
                        else:
                            print(f"  ✓ {table_name}: {table_count:,} 筆")
                    except Exception as e:
                        print(f"  ✗ {table_name}: 查詢失敗 ({e})")
            
            print("\n[Info] 所有中文別名 VIEW 建立完成！")
            print("[Info] 共建立 15 個 VIEW")
            print("\n[Info] 使用範例：")
            print("  SELECT 日期, 股票代號, 收盤價 FROM vw_tw_stock_price_data WHERE 股票代號 = '006208';")
            
        except Exception as e:
            conn.rollback()
            print(f"[Error] 建立 VIEW 失敗: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            conn.close()

