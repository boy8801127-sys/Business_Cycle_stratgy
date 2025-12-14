"""
[Orange 相關功能] 此檔案包含 Orange 機器學習模型整合

Orange 智能預測交易策略
純粹基於 Orange 模型預測的複合策略：動量 + 均值回歸 + 雙重確認 + 風險調整
"""

import os
import sys
import pandas as pd
import numpy as np

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 嘗試匯入 Orange 模型載入器（可選依賴）
try:
    from backtesting.orange_model_loader import OrangeModelLoader
    ORANGE_LOADER_AVAILABLE = True
except ImportError:
    ORANGE_LOADER_AVAILABLE = False
    OrangeModelLoader = None


class OrangePredictionStrategy:
    """
    [Orange 相關功能] Orange 智能預測交易策略
    
    基於 Orange 機器學習模型的複合交易策略，不依賴景氣燈號：
    - 動量策略（主要信號）：追蹤預測價格趨勢
    - 均值回歸策略（輔助過濾）：價格偏離預測值時進場
    - 雙重確認：需要連續3天預測都指向同一方向
    - 風險調整：根據預測穩定性動態調整倉位
    
    如果 Orange 模型不可用，策略不會執行（返回空訂單列表）
    """
    
    def __init__(self, stock_ticker='006208', hedge_ticker=None, model_path=None):
        """
        初始化 Orange 預測策略
        
        參數:
        - stock_ticker: 股票代號（預設 '006208'，富邦台50）
        - hedge_ticker: 避險資產代號（已移除，保留參數以保持兼容性）
        - model_path: Orange 模型文件路徑（預設 'orange_data_export/tree.pkcls'）
        """
        self.stock_ticker = stock_ticker
        self.hedge_ticker = None  # 已移除避險資產邏輯
        
        # 設定模型路徑
        if model_path is None:
            model_path = 'orange_data_export/tree.pkcls'
        self.model_path = model_path
        
        # 載入 Orange 模型（可選）
        self.model_loader = None
        self.model_available = False
        self.load_error = None
        
        if ORANGE_LOADER_AVAILABLE:
            try:
                if os.path.exists(self.model_path):
                    self.model_loader = OrangeModelLoader(self.model_path)
                    self.model_available = True
                    self.load_error = None
                    print(f"[Orange] 成功載入 Orange 模型: {self.model_path}")
                else:
                    self.model_available = False
                    self.load_error = f"模型文件不存在: {self.model_path}"
                    print(f"[Orange Warning] 模型文件不存在: {self.model_path}")
            except Exception as e:
                self.model_available = False
                self.load_error = str(e)
                print(f"[Orange Warning] 載入 Orange 模型失敗: {e}")
        else:
            self.model_available = False
            self.load_error = "Orange 模型載入器不可用"
            print(f"[Orange Warning] Orange 模型載入器不可用")
        
        # Orange 分析發現的 3 個重要特徵
        self.feature_names = [
            'signal_領先指標綜合指數',
            'coincident_海關出口值(十億元)',
            'lagging_全體金融機構放款與投資(10億元)'
        ]
        
        # 策略參數（已放寬以增加交易機會）
        self.momentum_lookback_days = 2  # 動量確認需要的天數（原3天）
        self.momentum_threshold_pct = 2.0  # 動量變化閾值（%，原3%）
        self.deviation_threshold_pct = 3.0  # 價格偏離閾值（%，原5%）
        self.stability_lookback_days = 7  # 計算穩定性的回顧天數
        self.max_volatility_for_full_position = 2.0  # 允許全倉的最大波動率（%）
    
    def _predict_price(self, row):
        """
        使用 Orange 模型預測收盤價
        
        參數:
        - row: 當天的資料行（包含所有指標）
        
        返回:
        - 預測的收盤價（如果模型可用且預測成功）
        - None（如果模型不可用或預測失敗）
        """
        if not self.model_available or self.model_loader is None:
            return None
        
        # 提取特徵
        feature_dict = {}
        for feature_name in self.feature_names:
            if feature_name in row:
                value = row[feature_name]
                # 檢查是否為有效數值
                if pd.notna(value):
                    feature_dict[feature_name] = float(value)
                else:
                    # 特徵缺失，無法預測
                    return None
            else:
                # 特徵不存在，無法預測
                return None
        
        # 轉換為 DataFrame
        feature_df = pd.DataFrame([feature_dict])
        
        try:
            # 使用模型預測
            predicted_price = self.model_loader.predict(feature_df)[0]
            return float(predicted_price)
        except Exception as e:
            # 預測失敗
            return None
    
    def _calculate_price_deviation(self, current_price, predicted_price):
        """
        計算當前價格相對於預測價格的偏離度
        
        參數:
        - current_price: 當前收盤價
        - predicted_price: 預測收盤價
        
        返回:
        - 偏離度（%），正值表示當前價格高於預測，負值表示低於預測
        - None 如果價格無效
        """
        if current_price is None or predicted_price is None:
            return None
        if current_price <= 0 or predicted_price <= 0:
            return None
        
        deviation = ((current_price - predicted_price) / predicted_price) * 100
        return deviation
    
    def _calculate_prediction_momentum(self, state, current_prediction):
        """
        計算預測動量（最近N天的預測價格變化趨勢）
        
        參數:
        - state: 策略狀態字典
        - current_prediction: 當前預測價格
        
        返回:
        - (momentum_direction, momentum_strength, momentum_confirmed)
        - momentum_direction: 'up', 'down', 或 None
        - momentum_strength: 動量強度（累積變化%）
        - momentum_confirmed: 是否確認（連續N天同方向）
        """
        if current_prediction is None or current_prediction <= 0:
            return None, 0.0, False
        
        # 初始化預測歷史
        if 'prediction_history' not in state:
            state['prediction_history'] = []
        
        prediction_history = state['prediction_history']
        
        # 添加當前預測到歷史
        prediction_history.append(current_prediction)
        
        # 只保留最近需要的天數
        max_history = max(self.momentum_lookback_days, self.stability_lookback_days)
        if len(prediction_history) > max_history:
            prediction_history = prediction_history[-max_history:]
            state['prediction_history'] = prediction_history
        
        # 如果歷史數據不足，無法計算動量
        if len(prediction_history) < self.momentum_lookback_days:
            return None, 0.0, False
        
        # 計算最近N天的動量
        recent_predictions = prediction_history[-self.momentum_lookback_days:]
        start_price = recent_predictions[0]
        end_price = recent_predictions[-1]
        
        # 計算累積變化率
        momentum_strength = ((end_price - start_price) / start_price) * 100
        
        # 檢查方向是否一致（所有變化都是同方向）
        direction_confirmed = True
        direction = None
        
        for i in range(1, len(recent_predictions)):
            change = recent_predictions[i] - recent_predictions[i-1]
            if change > 0:
                current_dir = 'up'
            elif change < 0:
                current_dir = 'down'
            else:
                current_dir = None
            
            if direction is None:
                direction = current_dir
            elif current_dir is not None and current_dir != direction:
                direction_confirmed = False
                break
        
        # 動量確認：方向一致且強度超過閾值
        momentum_confirmed = (
            direction_confirmed and 
            direction is not None and 
            abs(momentum_strength) >= self.momentum_threshold_pct
        )
        
        return direction, momentum_strength, momentum_confirmed
    
    def _check_momentum_signal(self, state, current_prediction):
        """
        檢查動量信號（雙重確認：連續N天確認）
        
        參數:
        - state: 策略狀態字典
        - current_prediction: 當前預測價格
        
        返回:
        - (signal, direction, strength)
        - signal: 'buy', 'sell', 或 None
        - direction: 'up' 或 'down'
        - strength: 動量強度
        """
        direction, strength, confirmed = self._calculate_prediction_momentum(state, current_prediction)
        
        if not confirmed:
            # 重置確認計數器
            state['momentum_confirmation'] = 0
            return None, None, 0.0
        
        # 更新確認計數器
        if 'momentum_confirmation' not in state:
            state['momentum_confirmation'] = 0
        if 'last_momentum_direction' not in state:
            state['last_momentum_direction'] = None
        
        # 如果方向改變，重置計數器
        if state['last_momentum_direction'] != direction:
            state['momentum_confirmation'] = 1
            state['last_momentum_direction'] = direction
        else:
            # 方向相同，增加計數
            state['momentum_confirmation'] += 1
        
        # 需要連續N天確認才產生信號
        if state['momentum_confirmation'] >= self.momentum_lookback_days:
            if direction == 'up':
                return 'buy', direction, strength
            elif direction == 'down':
                return 'sell', direction, strength
        
        return None, direction, strength
    
    def _calculate_prediction_stability(self, state):
        """
        計算預測穩定性（使用標準差）
        
        參數:
        - state: 策略狀態字典
        
        返回:
        - 波動率（標準差%），數值越大表示預測越不穩定
        """
        if 'prediction_history' not in state:
            return None
        
        prediction_history = state['prediction_history']
        
        if len(prediction_history) < self.stability_lookback_days:
            return None
        
        # 使用最近的N天數據
        recent_predictions = prediction_history[-self.stability_lookback_days:]
        
        # 計算標準差
        predictions_array = np.array(recent_predictions)
        mean_prediction = np.mean(predictions_array)
        
        if mean_prediction <= 0:
            return None
        
        std_dev = np.std(predictions_array)
        volatility_pct = (std_dev / mean_prediction) * 100
        
        return volatility_pct
    
    def _calculate_position_size(self, prediction_stability):
        """
        根據預測穩定性計算倉位大小
        
        參數:
        - prediction_stability: 預測波動率（%）
        
        返回:
        - 倉位大小（0.0 到 1.0）
        """
        if prediction_stability is None:
            # 如果無法計算穩定性，使用全倉
            return 1.0
        
        # 如果波動率低於閾值，使用全倉
        if prediction_stability <= self.max_volatility_for_full_position:
            return 1.0
        
        # 根據波動率調整倉位（波動率越高，倉位越小）
        # 線性遞減：波動率 2% = 100%倉位，波動率 10% = 20%倉位
        max_volatility = 10.0
        if prediction_stability >= max_volatility:
            return 0.2
        
        # 線性插值
        position_size = 1.0 - ((prediction_stability - self.max_volatility_for_full_position) / 
                               (max_volatility - self.max_volatility_for_full_position)) * 0.8
        
        return max(0.2, position_size)
    
    def _create_trade_step(self, reason, additional_conditions=None):
        """
        建立交易步驟資訊
        
        參數:
        - reason: 交易原因
        - additional_conditions: 額外條件列表 [{'name': str, 'value': float}, ...]
        
        返回:
        - 交易步驟字典
        """
        conditions = []
        
        if additional_conditions:
            conditions.extend(additional_conditions)
        
        return {
            'reason': reason,
            'conditions': conditions
        }
    
    def generate_orders(self, state, date, row, price_dict, positions=None, portfolio_value=None):
        """
        基於 Orange 預測的複合策略產生交易訂單
        
        策略邏輯：
        1. 動量策略（主要信號）：連續3天預測價格同方向變化且累積變化 >= 3%
        2. 均值回歸策略（輔助過濾）：當前價格偏離預測價格 >= 5%時作為過濾條件
        3. 風險調整：根據預測穩定性動態調整倉位
        
        交易條件：
        - 買進：動量向上確認 + 當前價格低於預測 >= 5% + 未持有
        - 賣出：動量向下確認 + 當前價格高於預測 >= 5% + 已持有
        
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
        
        # 如果模型不可用，直接返回空訂單列表（不執行策略）
        if not self.model_available:
            return orders
        
        # 獲取當前價格
        if 'close' not in row or pd.isna(row['close']) or row['close'] <= 0:
            return orders
        
        current_price = float(row['close'])
        
        # 使用 Orange 模型預測收盤價
        predicted_price = self._predict_price(row)
        
        if predicted_price is None:
            # 預測失敗，不執行交易
            return orders
        
        # 計算價格偏離度
        deviation = self._calculate_price_deviation(current_price, predicted_price)
        
        if deviation is None:
            return orders
        
        # 檢查動量信號（主要條件）
        momentum_signal, momentum_direction, momentum_strength = self._check_momentum_signal(
            state, predicted_price
        )
        
        # 計算預測穩定性
        prediction_stability = self._calculate_prediction_stability(state)
        position_size = self._calculate_position_size(prediction_stability)
        
        # 檢查是否持有股票
        is_holding = state.get('state', False)
        
        # 買進條件：動量向上確認 + 當前價格低於預測 >= 5% + 未持有
        if momentum_signal == 'buy':
            if deviation <= -self.deviation_threshold_pct and not is_holding:
                trade_step = self._create_trade_step('Orange動量+均值回歸買進', [
                    {'name': '預測價格', 'value': predicted_price},
                    {'name': '當前價格', 'value': current_price},
                    {'name': '價格偏離度(%)', 'value': deviation},
                    {'name': '動量方向', 'value': momentum_direction},
                    {'name': '動量強度(%)', 'value': momentum_strength},
                    {'name': '預測波動率(%)', 'value': prediction_stability if prediction_stability else 0},
                    {'name': '倉位大小(%)', 'value': position_size * 100}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': position_size,
                    'trade_step': trade_step,
                    'predicted_price': predicted_price,
                    'current_price': current_price,
                    'deviation_pct': deviation,
                    'momentum_strength': momentum_strength,
                    'position_size': position_size
                })
                state['state'] = True
        
        # 賣出條件：動量向下確認 + 當前價格高於預測 >= 5% + 已持有
        elif momentum_signal == 'sell':
            if deviation >= self.deviation_threshold_pct and is_holding:
                trade_step = self._create_trade_step('Orange動量+均值回歸賣出', [
                    {'name': '預測價格', 'value': predicted_price},
                    {'name': '當前價格', 'value': current_price},
                    {'name': '價格偏離度(%)', 'value': deviation},
                    {'name': '動量方向', 'value': momentum_direction},
                    {'name': '動量強度(%)', 'value': momentum_strength},
                    {'name': '預測波動率(%)', 'value': prediction_stability if prediction_stability else 0},
                    {'name': '倉位大小(%)', 'value': position_size * 100}
                ])
                orders.append({
                    'action': 'sell',
                    'ticker': self.stock_ticker,
                    'percent': position_size,
                    'trade_step': trade_step,
                    'predicted_price': predicted_price,
                    'current_price': current_price,
                    'deviation_pct': deviation,
                    'momentum_strength': momentum_strength,
                    'position_size': position_size
                })
                state['state'] = False
        
        return orders
