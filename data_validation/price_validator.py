"""
股價資料驗證模組
檢查股價異常（與前後幾天落差過大）
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_collection.database_manager import DatabaseManager


class PriceValidator:
    """股價資料驗證器"""
    
    def __init__(self, db_manager=None):
        """
        初始化驗證器
        
        參數:
        - db_manager: DatabaseManager 實例（可選）
        """
        self.db_manager = db_manager or DatabaseManager()
    
    def validate_stock_price(self, ticker, start_date=None, end_date=None, 
                            window_size=5, threshold_pct=20.0, market='both'):
        """
        驗證股票價格資料
        
        參數:
        - ticker: 股票代號
        - start_date: 起始日期（YYYYMMDD 或 YYYY-MM-DD）
        - end_date: 結束日期（YYYYMMDD 或 YYYY-MM-DD）
        - window_size: 檢查窗口大小（天數，預設5天）
        - threshold_pct: 異常閾值（百分比，預設20%）
        - market: 市場類型 ('listed', 'otc', 'both')
        
        回傳:
        - DataFrame: 包含異常記錄的資料
        """
        anomalies = []
        
        # 標準化日期格式
        if start_date:
            start_date = start_date.replace('-', '')
        if end_date:
            end_date = end_date.replace('-', '')
        
        # 檢查上市股票
        if market in ['listed', 'both']:
            df_listed = self.db_manager.get_stock_price(ticker=ticker, 
                                                         start_date=start_date, 
                                                         end_date=end_date)
            if not df_listed.empty:
                anomalies_listed = self._detect_anomalies(df_listed, ticker, 
                                                          window_size, threshold_pct, '上市')
                anomalies.extend(anomalies_listed)
        
        # 檢查上櫃股票
        if market in ['otc', 'both']:
            df_otc = self.db_manager.get_otc_stock_price(ticker=ticker,
                                                          start_date=start_date,
                                                          end_date=end_date)
            if not df_otc.empty:
                anomalies_otc = self._detect_anomalies(df_otc, ticker,
                                                        window_size, threshold_pct, '上櫃')
                anomalies.extend(anomalies_otc)
        
        if not anomalies:
            return pd.DataFrame()
        
        return pd.DataFrame(anomalies)
    
    def _detect_anomalies(self, df, ticker, window_size, threshold_pct, market_type):
        """
        偵測股價異常
        
        參數:
        - df: 股價資料 DataFrame
        - ticker: 股票代號
        - window_size: 窗口大小
        - threshold_pct: 異常閾值
        - market_type: 市場類型（'上市' 或 '上櫃'）
        
        回傳:
        - 異常記錄列表
        """
        anomalies = []
        
        # 確保資料按日期排序
        df = df.sort_values('date').copy()
        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
        df = df.dropna(subset=['date'])
        df = df.sort_values('date')
        
        # 使用收盤價進行檢查
        price_col = 'close'
        if price_col not in df.columns:
            return anomalies
        
        # 計算移動平均和標準差
        df['ma'] = df[price_col].rolling(window=window_size, center=True, min_periods=1).mean()
        df['std'] = df[price_col].rolling(window=window_size, center=True, min_periods=1).std()
        
        # 計算與前後幾天的差異
        for i in range(len(df)):
            if pd.isna(df.iloc[i][price_col]):
                continue
            
            current_price = df.iloc[i][price_col]
            current_date = df.iloc[i]['date']
            
            # 取得窗口內的價格（排除當天）
            window_start = max(0, i - window_size // 2)
            window_end = min(len(df), i + window_size // 2 + 1)
            window_prices = df.iloc[window_start:window_end][price_col].dropna().tolist()
            
            if len(window_prices) < 2:
                continue
            
            # 計算與窗口內其他價格的差異
            price_diffs = []
            for price in window_prices:
                if price != current_price:
                    diff_pct = abs((current_price - price) / price * 100)
                    price_diffs.append(diff_pct)
            
            if not price_diffs:
                continue
            
            # 計算平均差異
            avg_diff = np.mean(price_diffs)
            max_diff = np.max(price_diffs)
            
            # 如果差異超過閾值，標記為異常
            if max_diff > threshold_pct:
                # 取得前後幾天的價格作為參考
                prev_prices = []
                next_prices = []
                
                for j in range(max(0, i-2), i):
                    if j >= 0 and j < len(df) and not pd.isna(df.iloc[j][price_col]):
                        prev_prices.append(round(df.iloc[j][price_col], 2))
                
                for j in range(i+1, min(len(df), i+3)):
                    if j < len(df) and not pd.isna(df.iloc[j][price_col]):
                        next_prices.append(round(df.iloc[j][price_col], 2))
                
                anomaly = {
                    'ticker': ticker,
                    'date': current_date.strftime('%Y-%m-%d'),
                    'market': market_type,
                    'price': current_price,
                    'prev_prices': prev_prices,
                    'next_prices': next_prices,
                    'max_diff_pct': round(max_diff, 2),
                    'avg_diff_pct': round(avg_diff, 2),
                    'window_size': window_size
                }
                anomalies.append(anomaly)
        
        return anomalies
    
    def validate_multiple_stocks(self, tickers, start_date=None, end_date=None,
                                window_size=5, threshold_pct=20.0, market='both'):
        """
        批量驗證多檔股票
        
        參數:
        - tickers: 股票代號列表
        - 其他參數同 validate_stock_price
        
        回傳:
        - DataFrame: 包含所有異常記錄
        """
        all_anomalies = []
        
        for ticker in tickers:
            print(f"正在檢查 {ticker}...")
            anomalies = self.validate_stock_price(ticker, start_date, end_date,
                                                  window_size, threshold_pct, market)
            if not anomalies.empty:
                all_anomalies.append(anomalies)
        
        if not all_anomalies:
            return pd.DataFrame()
        
        return pd.concat(all_anomalies, ignore_index=True)
    
    def print_anomalies_report(self, anomalies_df):
        """
        列印異常報告（按日期分組顯示，簡化版）
        
        參數:
        - anomalies_df: 異常資料 DataFrame
        """
        if anomalies_df.empty:
            print("\n✓ 未發現異常資料")
            return
        
        print(f"\n{'='*80}")
        print(f"異常資料統計（總計 {len(anomalies_df)} 筆）")
        print(f"{'='*80}\n")
        
        # 按市場和日期分組
        grouped = anomalies_df.groupby(['market', 'date'])
        
        for (market, date), group in grouped:
            print(f"{market}市場在 日期:{date} 發現異常資料共 {len(group)} 筆")
            # 簡化顯示，只顯示股票代號和價格資訊
            tickers_info = []
            for idx, row in group.iterrows():
                tickers_info.append(f"{row['ticker']}(價格:{row['price']:.2f}, 最大差異:{row['max_diff_pct']:.2f}%)")
            print(f"  {' | '.join(tickers_info)}")
            print()
        
        print(f"{'='*80}")
    
    def delete_anomaly_data(self, anomalies_df):
        """
        刪除異常日期的所有資料（不限特定股票）
        
        參數:
        - anomalies_df: 異常資料 DataFrame
        
        回傳:
        - dict: 刪除結果統計
        """
        if anomalies_df.empty:
            return {'deleted': 0, 'errors': []}
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        deleted_count = 0
        errors = []
        
        try:
            # 按市場和日期分組（不分股票，刪除該日期的所有資料）
            grouped = anomalies_df.groupby(['market', 'date'])
            
            for (market, date), group in grouped:
                # 轉換日期格式為 YYYYMMDD
                date_str = date.replace('-', '')
                table_name = 'tw_stock_price_data' if market == '上市' else 'tw_otc_stock_price_data'
                
                try:
                    # 刪除該日期的所有資料（不限制特定股票）
                    cursor.execute(
                        f"DELETE FROM {table_name} WHERE date = ?",
                        (date_str,)
                    )
                    deleted_count += cursor.rowcount
                    print(f"    已刪除 {market} {date} 的所有資料（{cursor.rowcount} 筆）")
                except Exception as e:
                    errors.append(f"刪除 {market} {date} 失敗: {e}")
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            errors.append(f"刪除異常資料時發生錯誤: {e}")
        finally:
            conn.close()
        
        return {'deleted': deleted_count, 'errors': errors}
    
    def recollect_anomaly_data(self, anomalies_df):
        """
        重新蒐集異常日期的所有資料（不限特定股票）
        
        參數:
        - anomalies_df: 異常資料 DataFrame
        
        回傳:
        - dict: 重新蒐集結果統計
        """
        if anomalies_df.empty:
            return {'recollected': 0, 'errors': []}
        
        import time
        from data_collection.stock_data_collector import StockDataCollector
        from data_collection.otc_data_collector import OTCDataCollector
        
        # 按市場和日期分組（只記錄日期，不記錄特定股票）
        listed_dates = set()
        otc_dates = set()
        
        for _, row in anomalies_df.iterrows():
            date_str = row['date'].replace('-', '')  # YYYYMMDD
            
            if row['market'] == '上市':
                listed_dates.add(date_str)
            else:
                otc_dates.add(date_str)
        
        result = {'recollected': 0, 'errors': []}
        
        # 重新蒐集上市股票資料（該日期的所有資料）
        if listed_dates:
            try:
                collector = StockDataCollector(self.db_manager)
                listed_dates_list = sorted(list(listed_dates))
                for idx, date_str in enumerate(listed_dates_list, 1):
                    try:
                        print(f"  [{idx}/{len(listed_dates_list)}] 正在重新蒐集上市 {date_str} 的所有資料...")
                        df_date = collector.fetch_all_stocks_and_etf_daily_data(date_str)
                        if df_date is not None and not df_date.empty:
                            # 儲存該日期的所有資料（不過濾特定股票）
                            collector.save_tw_stock_price_data(df_date, date_str)
                            result['recollected'] += len(df_date)
                            print(f"    已重新蒐集 {len(df_date)} 筆資料")
                        else:
                            print(f"    [Warning] {date_str} 無資料可蒐集")
                        # 禮貌休息：每個日期請求後休息 5 秒（與原始蒐集邏輯一致）
                        if idx < len(listed_dates_list):
                            time.sleep(5)
                    except Exception as e:
                        error_msg = f"重新蒐集上市 {date_str} 失敗: {e}"
                        result['errors'].append(error_msg)
                        print(f"    [Error] {error_msg}")
                        # 即使失敗也要休息
                        if idx < len(listed_dates_list):
                            time.sleep(5)
            except Exception as e:
                result['errors'].append(f"重新蒐集上市資料時發生錯誤: {e}")
        
        # 重新蒐集上櫃股票資料（該日期的所有資料）
        if otc_dates:
            try:
                otc_collector = OTCDataCollector(self.db_manager)
                otc_dates_list = sorted(list(otc_dates))
                for idx, date_str in enumerate(otc_dates_list, 1):
                    try:
                        print(f"  [{idx}/{len(otc_dates_list)}] 正在重新蒐集上櫃 {date_str} 的所有資料...")
                        df_otc = otc_collector.fetch_daily_quotes(date_str)
                        if not df_otc.empty:
                            # 儲存該日期的所有資料（不過濾特定股票）
                            otc_collector.save_otc_stock_price_data(df_otc)
                            result['recollected'] += len(df_otc)
                            print(f"    已重新蒐集 {len(df_otc)} 筆資料")
                        else:
                            print(f"    [Warning] {date_str} 無資料可蒐集")
                        # 禮貌休息：每個日期請求後休息 5 秒（與原始蒐集邏輯一致）
                        if idx < len(otc_dates_list):
                            time.sleep(5)
                    except Exception as e:
                        error_msg = f"重新蒐集上櫃 {date_str} 失敗: {e}"
                        result['errors'].append(error_msg)
                        print(f"    [Error] {error_msg}")
                        # 即使失敗也要休息
                        if idx < len(otc_dates_list):
                            time.sleep(5)
            except Exception as e:
                result['errors'].append(f"重新蒐集上櫃資料時發生錯誤: {e}")
        
        return result
    
    def check_and_fix_missing_data(self, ticker='006208', start_date=None, end_date=None):
        """
        檢查交易日是否有指定股票的資料，如果沒有則刪除該日期的所有上市股票資料並重新蒐集
        
        參數:
        - ticker: 要檢查的股票代號（預設：006208）
        - start_date: 起始日期（YYYY-MM-DD 或 YYYYMMDD，預設：2015-01-01）
        - end_date: 結束日期（YYYY-MM-DD 或 YYYYMMDD，預設：今天）
        
        回傳:
        - dict: 檢查和修復結果統計
        """
        import pandas_market_calendars as pmc
        import time
        from data_collection.stock_data_collector import StockDataCollector
        
        # 設定日期範圍
        if start_date:
            start_date = start_date.replace('-', '')
            start_ts = pd.Timestamp(f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}")
        else:
            start_ts = pd.Timestamp('2015-01-01')
        
        if end_date:
            end_date = end_date.replace('-', '')
            end_ts = pd.Timestamp(f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}")
        else:
            end_ts = pd.Timestamp.now()
        
        # 取得交易日列表
        print(f"\n[步驟 1] 取得交易日列表（{start_ts.date()} 至 {end_ts.date()}）...")
        cal = pmc.get_calendar('XTAI')  # 台灣股市交易日曆
        trading_days = cal.valid_days(start_date=start_ts, end_date=end_ts)
        trading_days_str = [day.strftime('%Y%m%d') for day in trading_days]
        print(f"  共有 {len(trading_days_str)} 個交易日")
        
        # 取得資料庫中已有資料的交易日
        print(f"\n[步驟 2] 檢查哪些交易日缺少 {ticker} 的資料...")
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        # 取得資料庫中所有有上市股票資料的交易日
        cursor.execute("SELECT DISTINCT date FROM tw_stock_price_data ORDER BY date")
        existing_dates = set([row[0] for row in cursor.fetchall()])
        
        # 檢查每個交易日是否有指定股票的資料
        missing_dates = []
        for date_str in trading_days_str:
            if date_str in existing_dates:
                # 檢查該日期是否有指定股票的資料
                cursor.execute(
                    "SELECT COUNT(*) FROM tw_stock_price_data WHERE date = ? AND ticker = ?",
                    (date_str, ticker)
                )
                count = cursor.fetchone()[0]
                if count == 0:
                    missing_dates.append(date_str)
            else:
                # 如果該交易日完全沒有資料，也加入
                missing_dates.append(date_str)
        
        conn.close()
        
        if not missing_dates:
            print(f"\n✓ 所有交易日都有 {ticker} 的資料，無需修復")
            return {
                'checked': len(trading_days_str),
                'missing': 0,
                'deleted': 0,
                'recollected': 0,
                'errors': []
            }
        
        print(f"  發現 {len(missing_dates)} 個交易日缺少 {ticker} 的資料")
        print(f"  缺少資料的日期: {', '.join(missing_dates[:10])}{'...' if len(missing_dates) > 10 else ''}")
        
        # 詢問是否繼續
        confirm = input(f"\n是否要刪除這些日期的所有上市股票資料並重新蒐集？（y/n）: ").strip().lower()
        if confirm != 'y':
            print("已取消操作")
            return {
                'checked': len(trading_days_str),
                'missing': len(missing_dates),
                'deleted': 0,
                'recollected': 0,
                'errors': []
            }
        
        # 刪除缺少資料的日期的所有上市股票資料
        print(f"\n[步驟 3] 刪除缺少 {ticker} 資料的交易日之所有上市股票資料...")
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        deleted_count = 0
        errors = []
        
        for date_str in missing_dates:
            try:
                cursor.execute("DELETE FROM tw_stock_price_data WHERE date = ?", (date_str,))
                deleted_count += cursor.rowcount
            except Exception as e:
                errors.append(f"刪除 {date_str} 失敗: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"  已刪除 {deleted_count} 筆資料")
        
        # 重新蒐集這些日期的所有上市股票資料
        print(f"\n[步驟 4] 重新蒐集這些日期的所有上市股票資料...")
        collector = StockDataCollector(self.db_manager)
        recollected_count = 0
        
        for idx, date_str in enumerate(sorted(missing_dates), 1):
            try:
                print(f"  [{idx}/{len(missing_dates)}] 正在重新蒐集 {date_str}...")
                df_date = collector.fetch_all_stocks_and_etf_daily_data(date_str)
                if df_date is not None and not df_date.empty:
                    collector.save_tw_stock_price_data(df_date, date_str)
                    recollected_count += len(df_date)
                    print(f"    已重新蒐集 {len(df_date)} 筆資料")
                else:
                    print(f"    [Warning] {date_str} 無資料可蒐集")
                
                # 禮貌休息：每個日期請求後休息 5 秒
                if idx < len(missing_dates):
                    time.sleep(5)
            except Exception as e:
                error_msg = f"重新蒐集 {date_str} 失敗: {e}"
                errors.append(error_msg)
                print(f"    [Error] {error_msg}")
                # 即使失敗也要休息
                if idx < len(missing_dates):
                    time.sleep(5)
        
        print(f"\n{'='*60}")
        print("資料完整性檢查和修復完成")
        print(f"{'='*60}")
        print(f"檢查交易日數: {len(trading_days_str)}")
        print(f"缺少資料日期數: {len(missing_dates)}")
        print(f"刪除資料筆數: {deleted_count}")
        print(f"重新蒐集資料筆數: {recollected_count}")
        if errors:
            print(f"錯誤數: {len(errors)}")
            print("錯誤詳情:")
            for error in errors[:5]:  # 只顯示前5個錯誤
                print(f"  - {error}")
        
        return {
            'checked': len(trading_days_str),
            'missing': len(missing_dates),
            'deleted': deleted_count,
            'recollected': recollected_count,
            'errors': errors
        }
    
    def fill_zero_price_data(self, tickers, market='both', start_date=None, end_date=None):
        """
        填補零值價格資料（用於處理沒有交易的日子）
        
        對於指定股票，如果某天的 open, high, low, close 為 0（或接近 0），
        且 volume 為 0，則使用前一個有值日期的收盤價來填充價格欄位，
        並將 volume 和 turnover 設為 NULL。
        
        參數:
        - tickers: 股票代號列表或單一股票代號字串
        - market: 市場類型 ('listed', 'otc', 'both')，預設 'both'
        - start_date: 起始日期（YYYYMMDD 或 YYYY-MM-DD），None 表示全部
        - end_date: 結束日期（YYYYMMDD 或 YYYY-MM-DD），None 表示全部
        
        回傳:
        - dict: 包含處理結果的字典
        """
        # 標準化 tickers 為列表
        if isinstance(tickers, str):
            tickers = [tickers]
        tickers = [str(t).strip() for t in tickers if str(t).strip()]
        
        if not tickers:
            print("[Error] 請提供至少一個股票代號")
            return {'filled': 0, 'errors': ['未提供股票代號']}
        
        # 標準化日期格式
        if start_date:
            start_date = start_date.replace('-', '')
        if end_date:
            end_date = end_date.replace('-', '')
        
        result = {'filled': 0, 'errors': [], 'details': {}}
        
        # 處理上市股票
        if market in ['listed', 'both']:
            print(f"\n[上市市場] 開始處理 {len(tickers)} 檔股票...")
            for ticker in tickers:
                ticker_result = self._fill_price_for_ticker(
                    ticker, 'listed', start_date, end_date, treat_odd_lot=False
                )
                result['filled'] += ticker_result['filled']
                result['errors'].extend(ticker_result['errors'])
                result['details'][f'listed_{ticker}'] = ticker_result
        
        # 處理上櫃股票
        if market in ['otc', 'both']:
            print(f"\n[上櫃市場] 開始處理 {len(tickers)} 檔股票...")
            for ticker in tickers:
                ticker_result = self._fill_price_for_ticker(
                    ticker, 'otc', start_date, end_date, treat_odd_lot=False
                )
                result['filled'] += ticker_result['filled']
                result['errors'].extend(ticker_result['errors'])
                result['details'][f'otc_{ticker}'] = ticker_result
        
        return result

    def fill_odd_lot_price_data(self, tickers, market='both', start_date=None, end_date=None):
        """
        填補零股成交但無整股價的資料，使用前一個整股收盤價並標記 odd_lot_filled=1
        """
        if isinstance(tickers, str):
            tickers = [tickers]
        tickers = [str(t).strip() for t in tickers if str(t).strip()]
        if not tickers:
            print("[Error] 請提供至少一個股票代號")
            return {'filled': 0, 'errors': ['未提供股票代號']}
        
        if start_date:
            start_date = start_date.replace('-', '')
        if end_date:
            end_date = end_date.replace('-', '')
        
        result = {'filled': 0, 'errors': [], 'details': {}}
        
        if market in ['listed', 'both']:
            print(f"\n[上市市場] 開始處理零股價格 {len(tickers)} 檔股票...")
            for ticker in tickers:
                ticker_result = self._fill_price_for_ticker(
                    ticker, 'listed', start_date, end_date, treat_odd_lot=True
                )
                result['filled'] += ticker_result['filled']
                result['errors'].extend(ticker_result['errors'])
                result['details'][f'listed_{ticker}'] = ticker_result
        
        if market in ['otc', 'both']:
            print(f"\n[上櫃市場] 開始處理零股價格 {len(tickers)} 檔股票...")
            for ticker in tickers:
                ticker_result = self._fill_price_for_ticker(
                    ticker, 'otc', start_date, end_date, treat_odd_lot=True
                )
                result['filled'] += ticker_result['filled']
                result['errors'].extend(ticker_result['errors'])
                result['details'][f'otc_{ticker}'] = ticker_result
        
        return result
    
    def _fill_price_for_ticker(self, ticker, market_type, start_date, end_date, treat_odd_lot=False):
        """
        為單一股票填補價格資料
        treat_odd_lot: False -> 處理整張無成交的零值價格
                       True  -> 處理零股成交但缺少整股價格
        """
        table_name = 'tw_stock_price_data' if market_type == 'listed' else 'tw_otc_stock_price_data'
        market_name = '上市' if market_type == 'listed' else '上櫃'
        action_label = '零股價格' if treat_odd_lot else '零值價格'
        
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        try:
            query = f"""
                SELECT date, open, high, low, close, volume, turnover, odd_lot_filled
                FROM {table_name}
                WHERE ticker = ?
            """
            params = [ticker]
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            query += " ORDER BY date"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            if not rows:
                print(f"  [Warning] {market_name} {ticker}: 找不到資料")
                return {'filled': 0, 'errors': [], 'ticker': ticker, 'market': market_name}
            
            filled_count = 0
            errors = []
            last_valid_close = None
            
            for row in rows:
                date_str, open_val, high_val, low_val, close_val, volume_val, turnover_val, odd_flag = row
                
                is_zero_price = (
                    (open_val is None or abs(open_val) < 0.01) and
                    (high_val is None or abs(high_val) < 0.01) and
                    (low_val is None or abs(low_val) < 0.01) and
                    (close_val is None or abs(close_val) < 0.01)
                )
                has_volume = (
                    (volume_val is not None and volume_val > 0) or
                    (turnover_val is not None and turnover_val > 0)
                )
                
                target_condition = is_zero_price and (
                    (treat_odd_lot and has_volume and odd_flag != 1) or
                    (not treat_odd_lot and not has_volume)
                )
                
                if target_condition and last_valid_close is not None:
                    try:
                        if treat_odd_lot:
                            volume_update = volume_val
                            turnover_update = turnover_val
                            odd_flag_value = 1
                        else:
                            volume_update = None
                            turnover_update = None
                            odd_flag_value = 0
                        
                        cursor.execute(f"""
                            UPDATE {table_name}
                            SET open = ?,
                                high = ?,
                                low = ?,
                                close = ?,
                                volume = ?,
                                turnover = ?,
                                change = NULL,
                                odd_lot_filled = ?
                            WHERE ticker = ? AND date = ?
                        """, (
                            last_valid_close,
                            last_valid_close,
                            last_valid_close,
                            last_valid_close,
                            volume_update,
                            turnover_update,
                            odd_flag_value,
                            ticker,
                            date_str
                        ))
                        
                        filled_count += 1
                        if filled_count <= 5:
                            print(f"    {market_name} {ticker} {date_str}: {action_label}已填補為 {last_valid_close:.2f}")
                        elif filled_count == 6:
                            print("    ... (更多填補記錄將不再顯示)")
                    except Exception as e:
                        error_msg = f"{market_name} {ticker} {date_str}: 更新失敗 - {e}"
                        errors.append(error_msg)
                        if len(errors) <= 3:
                            print(f"    [Error] {error_msg}")
                
                if close_val is not None and abs(close_val) >= 0.01:
                    last_valid_close = close_val
            
            conn.commit()
            
            if filled_count > 0:
                print(f"  {market_name} {ticker}: 共填補 {filled_count} 筆{action_label}")
            
            return {
                'filled': filled_count,
                'errors': errors,
                'ticker': ticker,
                'market': market_name
            }
        
        except Exception as e:
            conn.rollback()
            error_msg = f"{market_name} {ticker}: 填補{action_label}失敗 - {e}"
            print(f"  [Error] {error_msg}")
            return {
                'filled': 0,
                'errors': [error_msg],
                'ticker': ticker,
                'market': market_name
            }
        finally:
            conn.close()
    
    def delete_warrants_from_otc(self):
        """
        從上櫃資料表中刪除權證資料（7開頭六位數的股票代號）
        
        回傳:
        - dict: 刪除結果統計
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        deleted_count = 0
        
        try:
            # 先查詢要被刪除的權證數量
            cursor.execute("""
                SELECT COUNT(*) 
                FROM tw_otc_stock_price_data
                WHERE ticker LIKE '7_____' 
                  AND LENGTH(ticker) = 6
                  AND ticker GLOB '[0-9]*'
            """)
            count_result = cursor.fetchone()
            total_to_delete = count_result[0] if count_result else 0
            
            if total_to_delete == 0:
                return {'deleted': 0, 'message': '沒有找到權證資料'}
            
            # 刪除所有 7 開頭的六位數代號（權證）
            cursor.execute("""
                DELETE FROM tw_otc_stock_price_data
                WHERE ticker LIKE '7_____' 
                  AND LENGTH(ticker) = 6
                  AND ticker GLOB '[0-9]*'
            """)
            deleted_count = cursor.rowcount
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            error_msg = f"刪除權證資料失敗: {e}"
            print(f"[Error] {error_msg}")
            return {'deleted': 0, 'errors': [error_msg]}
        finally:
            conn.close()
        
        return {'deleted': deleted_count}