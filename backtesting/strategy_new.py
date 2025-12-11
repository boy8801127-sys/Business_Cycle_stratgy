"""
新的景氣週期投資策略（基於 Orange 資料）
簡化版本，不需要處理發布日期、分批執行等複雜邏輯
"""


class CycleStrategyNew:
    """景氣週期策略基類（新版本）"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker=None):
        """
        初始化策略
        
        參數:
        - stock_ticker: 股票代號（預設 '006208'，富邦台50）
        - hedge_ticker: 避險資產代號（可選）
        """
        self.stock_ticker = stock_ticker
        self.hedge_ticker = hedge_ticker
    
    def _create_trade_step(self, reason, state, additional_conditions=None):
        """
        建立交易步驟資訊
        
        參數:
        - reason: 交易原因（例如：'藍燈買進'、'紅燈賣出'）
        - state: 策略狀態字典
        - additional_conditions: 額外條件列表 [{'name': str, 'value': float}, ...]
        
        返回:
        - 交易步驟字典 {'reason': str, 'conditions': [{'name': str, 'value': float}, ...]}
        """
        conditions = []
        
        # 添加景氣燈號分數
        score = state.get('score')
        if score is not None:
            conditions.append({'name': '景氣燈號分數', 'value': score})
        
        # 添加額外條件
        if additional_conditions:
            conditions.extend(additional_conditions)
        
        return {
            'reason': reason,
            'conditions': conditions
        }


class BuyAndHoldStrategyNew:
    """買進並持有策略（基準策略，新版本）"""
    
    def __init__(self, stock_ticker='006208'):
        """
        初始化策略
        
        參數:
        - stock_ticker: 股票代號（預設 '006208'，富邦台50）
        """
        self.stock_ticker = stock_ticker
        self.bought = False
    
    def generate_orders(self, state, date, row, price_dict, positions=None, portfolio_value=None):
        """
        買進並持有策略：只在第一次有機會時買進，之後不再交易
        
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
        
        # 只在第一次買進
        if not self.bought:
            if self.stock_ticker in price_dict:
                trade_step = {
                    'reason': '買進並持有',
                    'conditions': [
                        {'name': '策略類型', 'value': 'BuyAndHold'}
                    ]
                }
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': 1.0,  # 100% 買進
                    'trade_step': trade_step,
                    'signal_score': row.get('signal_景氣對策信號綜合分數'),
                    'signal_text': row.get('signal_景氣對策信號')
                })
                self.bought = True
        
        return orders


class ShortTermBondStrategyNew(CycleStrategyNew):
    """短天期美債避險策略（新版本）"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        """
        初始化策略
        
        參數:
        - stock_ticker: 股票代號（預設 '006208'，富邦台50）
        - hedge_ticker: 避險資產代號（預設 '00865B'，短期美債）
        """
        super().__init__(stock_ticker, hedge_ticker)
        self.first_trading_day = True  # 標記是否為第一個交易日
    
    def generate_orders(self, state, date, row, price_dict, positions=None, portfolio_value=None):
        """
        短天期美債避險策略：藍燈買進股票，紅燈賣出股票並買進避險資產
        
        參數:
        - state: 策略狀態字典
        - date: 交易日期
        - row: 當天的資料行（包含所有指標，已對齊）
        - price_dict: 價格字典 {ticker: close}
        - positions: 當前持倉字典（可選）
        - portfolio_value: 當前投資組合總價值（可選）
        
        返回:
        - 訂單列表
        """
        orders = []
        score = state.get('score')
        
        # 取得燈號分數和文字（用於交易記錄）
        signal_score = row.get('signal_景氣對策信號綜合分數')
        signal_text = row.get('signal_景氣對策信號')
        
        # 回測開始時，在第一個交易日分批買進股票
        if self.first_trading_day:
            if self.stock_ticker in price_dict:
                trade_step = self._create_trade_step('回測開始買進', state)
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': 1.0,
                    'split_execution': True,  # 標記需要分批執行
                    'trade_step': trade_step,
                    'signal_score': signal_score,
                    'signal_text': signal_text
                })
                state['state'] = True
                self.first_trading_day = False
        
        if score is None:
            return orders
        
        # 藍燈（9-16分）：買進股票，賣出避險資產
        if 9 <= score <= 16:
            # 如果沒有持有股票，買進（分批執行）
            if not state.get('state', False):
                trade_step = self._create_trade_step('藍燈買進', state)
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': 1.0,
                    'split_execution': True,  # 標記需要分批執行
                    'trade_step': trade_step,
                    'signal_score': signal_score,
                    'signal_text': signal_text
                })
                state['state'] = True
            
            # 如果有避險資產且持有，賣出（分批執行）
            if self.hedge_ticker and state.get('hedge_state', False):
                hedge_trade_step = self._create_trade_step('藍燈賣出避險資產', state)
                orders.append({
                    'action': 'sell',
                    'ticker': self.hedge_ticker,
                    'percent': 1.0,
                    'split_execution': True,  # 標記需要分批執行
                    'trade_step': hedge_trade_step,
                    'signal_score': signal_score,
                    'signal_text': signal_text
                })
                state['hedge_state'] = False
        
        # 紅燈（≥38分）：賣出股票，買進避險資產
        elif score >= 38:
            # 如果持有股票，賣出（分批執行）
            if state.get('state', False):
                hedge_trade_step = self._create_trade_step('紅燈買進避險資產', state)
                trade_step = self._create_trade_step('紅燈賣出', state)
                orders.append({
                    'action': 'sell',
                    'ticker': self.stock_ticker,
                    'percent': 1.0,
                    'split_execution': True,  # 標記需要分批執行
                    'trigger_hedge_buy': True,  # 標記需要買進避險資產
                    'hedge_ticker': self.hedge_ticker,
                    'trade_step': trade_step,
                    'hedge_trade_step': hedge_trade_step,  # 供引擎使用
                    'signal_score': signal_score,
                    'signal_text': signal_text
                })
                state['state'] = False
                if self.hedge_ticker:
                    state['hedge_state'] = True
        
        return orders

