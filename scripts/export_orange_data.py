"""
輸出 Orange 分析數據腳本
將股價數據（006208、2330）與領先/同時/落後指標合併，輸出為長格式 CSV
"""

import os
import sys
import pandas as pd
from datetime import datetime

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collection.database_manager import DatabaseManager


def load_indicator_data():
    """讀取所有指標數據（領先、同時、落後、綜合指標）"""
    base_path = 'business_cycle'
    
    # 讀取領先指標構成項目
    leading_path = os.path.join(base_path, '領先指標構成項目.csv')
    leading_df = pd.read_csv(leading_path, encoding='utf-8')
    leading_df['indicator_date'] = pd.to_datetime(leading_df['Date'], format='%Y%m')
    # 添加前綴
    leading_cols = {col: f'leading_{col}' for col in leading_df.columns if col not in ['Date', 'indicator_date']}
    leading_df = leading_df.rename(columns=leading_cols)
    
    # 讀取同時指標構成項目
    coincident_path = os.path.join(base_path, '同時指標構成項目.csv')
    coincident_df = pd.read_csv(coincident_path, encoding='utf-8')
    coincident_df['indicator_date'] = pd.to_datetime(coincident_df['Date'], format='%Y%m')
    # 添加前綴
    coincident_cols = {col: f'coincident_{col}' for col in coincident_df.columns if col not in ['Date', 'indicator_date']}
    coincident_df = coincident_df.rename(columns=coincident_cols)
    
    # 讀取落後指標構成項目
    lagging_path = os.path.join(base_path, '落後指標構成項目.csv')
    lagging_df = pd.read_csv(lagging_path, encoding='utf-8')
    lagging_df['indicator_date'] = pd.to_datetime(lagging_df['Date'], format='%Y%m')
    # 添加前綴
    lagging_cols = {col: f'lagging_{col}' for col in lagging_df.columns if col not in ['Date', 'indicator_date']}
    lagging_df = lagging_df.rename(columns=lagging_cols)
    
    # 讀取景氣指標與燈號（包含綜合指數和燈號分數）
    signal_path = os.path.join(base_path, '景氣指標與燈號.csv')
    signal_df = pd.read_csv(signal_path, encoding='utf-8')
    signal_df['indicator_date'] = pd.to_datetime(signal_df['Date'], format='%Y%m')
    # 添加前綴
    signal_cols = {col: f'signal_{col}' for col in signal_df.columns if col not in ['Date', 'indicator_date']}
    signal_df = signal_df.rename(columns=signal_cols)
    
    # 合併所有指標數據（使用 inner join 確保所有指標都有相同的日期）
    merged_indicators = leading_df.merge(
        coincident_df[['indicator_date'] + [col for col in coincident_df.columns if col.startswith('coincident_')]],
        on='indicator_date',
        how='inner'
    ).merge(
        lagging_df[['indicator_date'] + [col for col in lagging_df.columns if col.startswith('lagging_')]],
        on='indicator_date',
        how='inner'
    ).merge(
        signal_df[['indicator_date'] + [col for col in signal_df.columns if col.startswith('signal_')]],
        on='indicator_date',
        how='inner'
    )
    
    # 按日期排序
    merged_indicators = merged_indicators.sort_values('indicator_date').reset_index(drop=True)
    
    return merged_indicators


def get_indicator_for_date(target_date, indicator_df):
    """
    根據目標日期，取得往前推2個月的指標數據
    
    參數:
    - target_date: 目標日期（datetime）
    - indicator_df: 指標數據 DataFrame（包含 indicator_date 欄位）
    
    返回:
    - Series: 對應的指標數據
    """
    # 計算往前推2個月的日期（該月份的第一天）
    target_month = target_date.replace(day=1)
    
    # 使用 pandas 的 DateOffset 來往前推2個月
    indicator_month = target_month - pd.DateOffset(months=2)
    
    # 在指標數據中查找對應月份的數據
    # 找到 indicator_date 與 indicator_month 相同月份的數據
    mask = (indicator_df['indicator_date'].dt.year == indicator_month.year) & \
           (indicator_df['indicator_date'].dt.month == indicator_month.month)
    
    matching_rows = indicator_df[mask]
    
    if len(matching_rows) > 0:
        # 返回第一筆匹配的數據（應該只有一筆，因為是月數據）
        return matching_rows.iloc[0]
    else:
        # 如果找不到，返回空 Series
        return pd.Series(dtype=float)


def export_orange_data():
    """主函數：輸出 Orange 分析數據"""
    print("\n[輸出 Orange 分析數據]")
    print("-" * 60)
    
    # 設定時間範圍
    start_date_str = '2020-01-01'
    end_date = datetime.now()
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    print(f"時間範圍：{start_date_str} 至 {end_date_str}")
    
    # 初始化數據庫管理器
    db_manager = DatabaseManager()
    
    # 讀取股價數據
    print("\n正在讀取股價數據...")
    tickers = ['006208', '2330']
    
    stock_data_list = []
    for ticker in tickers:
        print(f"  讀取 {ticker}...")
        df = db_manager.get_stock_price(
            ticker=ticker,
            start_date=start_date_str.replace('-', ''),
            end_date=end_date_str.replace('-', '')
        )
        if not df.empty:
            # 轉換日期格式
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
            # 只保留需要的欄位
            df = df[['date', 'ticker', 'close']].copy()
            stock_data_list.append(df)
    
    if not stock_data_list:
        print("[Error] 無法讀取股價數據")
        return
    
    # 合併所有股票的數據
    stock_data = pd.concat(stock_data_list, ignore_index=True)
    stock_data = stock_data.sort_values(['date', 'ticker']).reset_index(drop=True)
    print(f"  共讀取 {len(stock_data)} 筆股價數據")
    
    # 讀取指標數據
    print("\n正在讀取指標數據...")
    indicator_df = load_indicator_data()
    print(f"  共讀取 {len(indicator_df)} 筆指標數據（從 {indicator_df['indicator_date'].min()} 至 {indicator_df['indicator_date'].max()}）")
    
    # 合併數據：為每個股價日期添加對應的指標數據（n-2個月）
    print("\n正在合併數據（指標對齊：n-2個月）...")
    
    result_rows = []
    indicator_cols = [col for col in indicator_df.columns if col != 'indicator_date']
    
    for idx, row in stock_data.iterrows():
        if idx % 1000 == 0:
            print(f"  處理進度：{idx}/{len(stock_data)} ({idx/len(stock_data)*100:.1f}%)")
        
        target_date = row['date']
        indicator_row = get_indicator_for_date(target_date, indicator_df)
        
        # 建立結果行
        result_row = {
            'date': target_date.strftime('%Y-%m-%d'),
            'ticker': row['ticker'],
            'close': row['close']
        }
        
        # 添加指標數據
        for col in indicator_cols:
            result_row[col] = indicator_row.get(col, None)
        
        result_rows.append(result_row)
    
    # 轉換為 DataFrame
    result_df = pd.DataFrame(result_rows)
    
    # 確保欄位順序：date, ticker, close, 然後是指標欄位
    column_order = ['date', 'ticker', 'close'] + indicator_cols
    result_df = result_df[column_order]
    
    # 特徵工程：添加日報酬率和時間特徵
    print("\n正在計算特徵工程...")
    
    # 轉換日期為 datetime 類型（如果還沒有）
    result_df['date_dt'] = pd.to_datetime(result_df['date'])
    
    # 按股票代號和日期排序，確保順序正確
    result_df = result_df.sort_values(['ticker', 'date_dt']).reset_index(drop=True)
    
    # 計算日報酬率（按股票分組）
    print("  計算日報酬率...")
    result_df['daily_return'] = result_df.groupby('ticker')['close'].pct_change()
    
    # 計算累積報酬率（從起始日期開始）
    print("  計算累積報酬率...")
    # 使用 apply 但重置索引以確保對齊
    cumulative_returns = result_df.groupby('ticker')['daily_return'].apply(
        lambda x: (1 + x.fillna(0)).cumprod() - 1
    ).reset_index(level=0, drop=True)
    result_df['cumulative_return'] = cumulative_returns.values
    
    # 添加時間特徵
    print("  添加時間特徵...")
    result_df['year'] = result_df['date_dt'].dt.year
    result_df['month'] = result_df['date_dt'].dt.month
    result_df['quarter'] = result_df['date_dt'].dt.quarter
    result_df['day_of_week'] = result_df['date_dt'].dt.dayofweek  # 0=Monday, 6=Sunday
    result_df['is_month_start'] = result_df['date_dt'].dt.is_month_start.astype(int)
    result_df['is_month_end'] = result_df['date_dt'].dt.is_month_end.astype(int)
    
    # 移除臨時的 date_dt 欄位（如果存在）
    if 'date_dt' in result_df.columns:
        result_df = result_df.drop(columns=['date_dt'])
    
    # 重新排列欄位順序：date, ticker, close, daily_return, cumulative_return, 時間特徵, 然後是指標欄位
    time_features = ['year', 'month', 'quarter', 'day_of_week', 'is_month_start', 'is_month_end']
    column_order = ['date', 'ticker', 'close', 'daily_return', 'cumulative_return'] + time_features + indicator_cols
    result_df = result_df[column_order]
    
    # 輸出 CSV 文件
    output_path = 'results/orange_analysis_data.csv'
    os.makedirs('results', exist_ok=True)
    
    print(f"\n正在輸出 CSV 文件：{output_path}")
    result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\n[完成] 成功輸出 {len(result_df)} 筆數據")
    print(f"  欄位數量：{len(result_df.columns)}")
    print(f"  日期範圍：{result_df['date'].min()} 至 {result_df['date'].max()}")
    print(f"  股票代號：{sorted(result_df['ticker'].unique())}")
    print(f"\n前 5 筆數據預覽：")
    print(result_df.head())
    
    return output_path


if __name__ == '__main__':
    export_orange_data()

