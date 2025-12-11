"""
TEJ 台灣經濟新報對照組策略
獨立策略檔案，不與現有回測系統混用
基於固定日期的買賣策略
"""

from datetime import date
import pandas as pd


class TEJStrategy:
    """TEJ 策略：基於固定日期的買賣"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        """
        初始化策略
        
        參數:
        - stock_ticker: 股票代號（預設 '006208'，富邦台50）
        - hedge_ticker: 避險資產代號（預設 '00865B'，短期美債）
        """
        self.stock_ticker = stock_ticker
        self.hedge_ticker = hedge_ticker
        
        # 定義固定交易日期和動作
        self.trade_dates = {
            date(2020, 1, 2): {
                'stock_action': 'buy',
                'hedge_action': None,
                'score': 27.0,
                'reason': '初始建倉'
            },
            date(2021, 2, 26): {
                'stock_action': 'sell',
                'hedge_action': 'buy',
                'score': 40.0,
                'reason': '紅燈賣出並買入債券避險'
            },
            date(2022, 11, 30): {
                'stock_action': 'buy',
                'hedge_action': 'sell',
                'score': 12.0,
                'reason': '藍燈買進並賣出債券'
            },
            date(2024, 6, 28): {
                'stock_action': 'sell',
                'hedge_action': 'buy',
                'score': 38.0,
                'reason': '紅燈賣出並買入債券避險'
            }
        }
    
    def _create_trade_step(self, reason, score):
        """
        建立交易步驟資訊
        
        參數:
        - reason: 交易原因（例如：'藍燈買進'、'紅燈賣出'）
        - score: 景氣燈號分數
        
        返回:
        - 交易步驟字典
        """
        return {
            'reason': reason,
            'conditions': [
                {'name': '景氣燈號分數', 'value': score}
            ]
        }
    
    def generate_orders(self, state, date, row, price_dict, positions=None, portfolio_value=None):
        """
        TEJ 策略：基於固定日期的買賣
        
        參數:
        - state: 策略狀態字典（此策略不使用）
        - date: 交易日期
        - row: 當天的資料行（包含所有指標，已對齊）
        - price_dict: 價格字典 {ticker: close}
        - positions: 當前持倉字典（可選）
        - portfolio_value: 當前投資組合總價值（可選）
        
        返回:
        - 訂單列表
        """
        orders = []
        
        # 將 date 轉換為 date 對象（如果它是 datetime 或其他格式）
        if hasattr(date, 'date'):
            trade_date = date.date()
        elif isinstance(date, str):
            trade_date = pd.to_datetime(date).date()
        else:
            trade_date = date
        
        # 檢查是否為交易日期
        if trade_date not in self.trade_dates:
            return orders
        
        trade_info = self.trade_dates[trade_date]
        score = trade_info['score']
        reason = trade_info['reason']
        
        # 取得燈號分數和文字（用於交易記錄）
        signal_score = row.get('signal_景氣對策信號綜合分數', score)
        signal_text = row.get('signal_景氣對策信號', '')
        
        # 先處理賣出訂單（獲得現金），然後再處理買進訂單（使用現金）
        # 這樣可以確保在同一天需要同時買賣時，先有現金再買進
        
        # 1. 處理債券賣出（如果有的話）
        if trade_info['hedge_action'] == 'sell':
            if self.hedge_ticker and self.hedge_ticker in price_dict:
                hedge_trade_step = self._create_trade_step('賣出債券', score)
                orders.append({
                    'action': 'sell',
                    'ticker': self.hedge_ticker,
                    'percent': 1.0,  # 100% 賣出
                    'trade_step': hedge_trade_step,
                    'signal_score': signal_score,
                    'signal_text': signal_text
                })
        
        # 2. 處理股票賣出（如果有的話）
        if trade_info['stock_action'] == 'sell':
            if self.stock_ticker in price_dict:
                trade_step = self._create_trade_step(reason, score)
                hedge_trade_step = None
                
                # 如果需要同時買進債券
                if trade_info['hedge_action'] == 'buy':
                    hedge_trade_step = self._create_trade_step('買入債券避險', score)
                
                orders.append({
                    'action': 'sell',
                    'ticker': self.stock_ticker,
                    'percent': 1.0,  # 100% 賣出
                    'trigger_hedge_buy': trade_info['hedge_action'] == 'buy',
                    'hedge_ticker': self.hedge_ticker if trade_info['hedge_action'] == 'buy' else None,
                    'trade_step': trade_step,
                    'hedge_trade_step': hedge_trade_step,
                    'signal_score': signal_score,
                    'signal_text': signal_text
                })
        
        # 3. 處理股票買進（在賣出之後，確保有現金）
        if trade_info['stock_action'] == 'buy':
            if self.stock_ticker in price_dict:
                trade_step = self._create_trade_step(reason, score)
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': 1.0,  # 100% 買進
                    'trade_step': trade_step,
                    'signal_score': signal_score,
                    'signal_text': signal_text
                })
        
        return orders

