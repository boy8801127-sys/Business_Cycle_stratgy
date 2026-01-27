"""
TEJ 台灣經濟新報對照組策略回測腳本
獨立執行，不依賴主選單，不與現有回測系統混用
"""

import os
import sys
from datetime import datetime
import pandas as pd

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtesting.backtest_engine_new import BacktestEngineNew
from backtesting.strategy_tej import TEJStrategy
import pandas as pd


def normalize_ticker(ticker):
    """
    標準化 ticker 格式：6208 -> 006208, 0050 -> 000050
    """
    if pd.isna(ticker):
        return None
    
    # 處理浮點數格式（如 6208.0 -> 6208）
    if isinstance(ticker, (int, float)):
        ticker = int(ticker)
    
    ticker_str = str(ticker)
    
    # 如果是 4 位數字，轉換為 6 位（6208 -> 006208, 0050 -> 000050）
    if len(ticker_str) == 4 and ticker_str.isdigit():
        return '00' + ticker_str
    
    return ticker_str


def run_tej_backtest():
    """執行 TEJ 策略回測"""
    print("\n" + "=" * 60)
    print("TEJ 台灣經濟新報對照組策略回測")
    print("=" * 60)
    
    # 固定參數
    initial_capital = 1000000  # 100萬
    start_date = '2020-01-01'
    end_date = '2025-12-31'
    stock_ticker_input = '006208'  # 富邦台50（輸入格式）
    hedge_ticker = '00865B'  # 短期美債
    
    # 標準化 ticker（006208 已經是 6 位數，不需要轉換）
    stock_ticker = normalize_ticker(stock_ticker_input)
    
    print(f"\n回測參數：")
    print(f"  初始資金：{initial_capital:,} 元")
    print(f"  回測期間：{start_date} 至 {end_date}")
    print(f"  股票代號：{stock_ticker_input} -> {stock_ticker}（標準化後）")
    print(f"  債券代號：{hedge_ticker}")
    print(f"\n策略邏輯：基於固定日期的買賣")
    print(f"  - 2020-01-02: 買進 006208 (Score: 27.0)")
    print(f"  - 2021-02-26: 賣出 006208 (Score: 40.0), 買入債券避險")
    print(f"  - 2022-11-30: 買進 006208 (Score: 12.0), 賣出債券")
    print(f"  - 2024-06-28: 賣出 006208 (Score: 38.0), 買入債券避險")
    
    # 建立策略實例（使用標準化後的 ticker）
    strategy = TEJStrategy(stock_ticker=stock_ticker, hedge_ticker=hedge_ticker)
    print(f"[Debug] 策略使用的股票代號：{strategy.stock_ticker}")
    
    # 包裝策略函數
    def strategy_func(state, date, row, price_dict, positions=None, portfolio_value=None):
        return strategy.generate_orders(state, date, row, price_dict, positions, portfolio_value)
    
    # 建立回測引擎
    engine = BacktestEngineNew(initial_capital=initial_capital)
    
    # 執行回測
    print(f"\n開始執行回測...")
    try:
        results = engine.run_backtest(
            start_date=start_date,
            end_date=end_date,
            strategy_func=strategy_func,
            tickers=[stock_ticker, hedge_ticker]
        )
        
        # 顯示結果摘要
        print("\n" + "=" * 60)
        print("回測結果摘要")
        print("=" * 60)
        print(f"初始資金：{initial_capital:,} 元")
        print(f"最終價值：{results['final_value']:,.0f} 元")
        print(f"總報酬率：{results['total_return']:.2%}")
        
        # 從 metrics 中取得指標
        metrics = results.get('metrics', {})
        if metrics:
            print(f"年化報酬率：{metrics.get('annualized_return', 0):.2%}")
            print(f"最大回撤：{metrics.get('max_drawdown', 0):.2%}")
            print(f"夏普比率：{metrics.get('sharpe_ratio', 0):.2f}")
        else:
            print(f"年化報酬率：0.00%")
            print(f"最大回撤：0.00%")
            print(f"夏普比率：0.00")
        
        print(f"總交易次數：{len(engine.trades)} 筆")
        
        # 產生持倉變動摘要
        position_summary = engine.generate_position_summary()
        
        # 輸出交易記錄
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = 'results'
        os.makedirs(output_dir, exist_ok=True)
        
        # 儲存交易記錄
        if engine.trades:
            trades_df = pd.DataFrame(engine.trades)
            trades_file = os.path.join(output_dir, f'position_changes_TEJ_{timestamp}.csv')
            trades_df.to_csv(trades_file, index=False, encoding='utf-8-sig')
            print(f"\n交易記錄已儲存至：{trades_file}")
        
        # 儲存每日報酬率
        if engine.dates and engine.returns:
            daily_returns_data = {
                '日期': engine.dates,
                '投資組合價值': engine.portfolio_value,
                '日報酬率(%)': [r * 100 for r in engine.returns],
                '累積報酬率(%)': [
                    ((v / initial_capital) - 1) * 100 for v in engine.portfolio_value
                ]
            }
            daily_returns_df = pd.DataFrame(daily_returns_data)
            daily_returns_file = os.path.join(output_dir, f'daily_returns_TEJ_{timestamp}.csv')
            daily_returns_df.to_csv(daily_returns_file, index=False, encoding='utf-8-sig')
            print(f"每日報酬率已儲存至：{daily_returns_file}")
        
        # 顯示交易記錄摘要（按照 TEJ 格式）
        print("\n" + "=" * 60)
        print("進入景氣循環")
        print("=" * 60)
        if engine.trades:
            for trade in engine.trades:
                date_str = trade.get('日期', '')
                action = trade.get('動作', '')
                ticker = trade.get('標的代號', '')
                score = trade.get('景氣燈號分數', '')
                signal_text = trade.get('景氣燈號', '')
                
                # 格式化日期
                if isinstance(date_str, datetime):
                    date_str = date_str.strftime('%Y-%m-%d')
                elif hasattr(date_str, 'strftime'):
                    date_str = date_str.strftime('%Y-%m-%d')
                elif isinstance(date_str, str):
                    # 如果已經是字串，嘗試解析
                    try:
                        date_obj = pd.to_datetime(date_str)
                        date_str = date_obj.strftime('%Y-%m-%d')
                    except:
                        pass
                
                # 格式化分數
                if pd.notna(score):
                    score_str = f"{float(score):.1f}"
                else:
                    score_str = "N/A"
                
                # 根據動作顯示不同訊息
                if action == '買進':
                    # 顯示原始 ticker（0050）而不是標準化後的（000050）
                    display_ticker = stock_ticker_input if ticker == stock_ticker else ticker
                    print(f"Date: {date_str}, Score: {score_str}, 買進 {display_ticker}")
                elif action == '賣出':
                    # 顯示原始 ticker（0050）而不是標準化後的（000050）
                    display_ticker = stock_ticker_input if ticker == stock_ticker else ticker
                    print(f"Date: {date_str}, Score: {score_str}, 賣出 {display_ticker}")
                    # 如果是賣出股票，檢查是否有買進債券的交易
                    if ticker == stock_ticker:
                        # 查找同一天的債券買進交易
                        for hedge_trade in engine.trades:
                            hedge_date = hedge_trade.get('日期', '')
                            hedge_action = hedge_trade.get('動作', '')
                            hedge_ticker_code = hedge_trade.get('標的代號', '')
                            
                            # 格式化日期以便比較
                            if isinstance(hedge_date, datetime):
                                hedge_date_str = hedge_date.strftime('%Y-%m-%d')
                            elif hasattr(hedge_date, 'strftime'):
                                hedge_date_str = hedge_date.strftime('%Y-%m-%d')
                            elif isinstance(hedge_date, str):
                                try:
                                    hedge_date_obj = pd.to_datetime(hedge_date)
                                    hedge_date_str = hedge_date_obj.strftime('%Y-%m-%d')
                                except:
                                    hedge_date_str = str(hedge_date)
                            else:
                                hedge_date_str = str(hedge_date)
                            
                            if hedge_date_str == date_str and hedge_action == '買進' and hedge_ticker_code == hedge_ticker:
                                hedge_score = hedge_trade.get('景氣燈號分數', '')
                                if pd.notna(hedge_score):
                                    hedge_score_str = f"{float(hedge_score):.1f}"
                                else:
                                    hedge_score_str = score_str
                                print(f"Date: {date_str}, Score: {hedge_score_str}，買入債券避險")
                                break
                elif action == '賣出' and ticker == hedge_ticker:
                    # 賣出債券的情況
                    print(f"Date: {date_str}, Score: {score_str}，賣出債券")
        else:
            print("無交易記錄")
        
        print("\n" + "=" * 60)
        print("回測完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[Error] 回測執行失敗：{e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    run_tej_backtest()

