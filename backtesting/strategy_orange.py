"""
[Orange 相關功能] 此檔案包含 Orange 機器學習模型整合

Orange 智能預測交易策略
純均值回歸策略：基於價格偏離預測價格的程度進行交易
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
    
    純均值回歸策略，基於 Orange 機器學習模型的價格預測：
    - 均值回歸策略：當實際價格偏離預測價格超過閾值時進行交易
    - 風險調整：根據預測穩定性動態調整倉位大小
    
    交易邏輯：
    - 買進：當前價格 < 預測價格 × (1 - 閾值%) 且未持有
    - 賣出：當前價格 > 預測價格 × (1 + 閾值%) 且已持有
    
    如果 Orange 模型不可用，策略不會執行（返回空訂單列表）
    """
    
    def __init__(self, stock_ticker='006208', hedge_ticker=None, model_path=None, 
                 use_multi_model=False, model_price_ranges=None):
        """
        初始化 Orange 預測策略
        
        參數:
        - stock_ticker: 股票代號（預設 '006208'，富邦台50）
        - hedge_ticker: 避險資產代號（已移除，保留參數以保持兼容性）
        - model_path: Orange 模型文件路徑（預設 'orange_data_export/tree.pkcls'）
                     如果 use_multi_model=True，此參數會被忽略
        - use_multi_model: 是否使用多模型（根據價格範圍選擇，預設 False）
        - model_price_ranges: 多模型價格範圍配置（預設 None，會使用預設配置）
                            格式: [(min_price, max_price, model_path), ...]
        """
        self.stock_ticker = stock_ticker
        self.hedge_ticker = None  # 已移除避險資產邏輯
        self.use_multi_model = use_multi_model
        
        # 載入 Orange 模型（可選）
        self.model_loader = None
        self.model_loaders = {}  # 多模型載入器字典 {model_name: loader}
        self.model_available = False
        self.load_error = None
        
        if ORANGE_LOADER_AVAILABLE:
            if use_multi_model:
                # 使用多模型模式
                if model_price_ranges is None:
                    # 預設配置：三個模型，根據價格範圍選擇
                    # tree3: 47.1±12.2 ~ 79.7±0.6 (約 34.9 ~ 80.3) - 低價群組
                    # tree2: 77.6±3.5 ~ 111.5±19.6 (約 74.1 ~ 131.1) - 中價群組
                    # tree: 104.1±15.3 ~ 144.6±20.6 (約 88.8 ~ 165.2) - 高價群組
                    model_price_ranges = [
                        (0, 80, 'orange_data_export/tree3.pkcls'),      # 低價群組（tree3: 34.9 ~ 80.3）
                        (80, 132, 'orange_data_export/tree2.pkcls'),     # 中價群組（tree2: 74.1 ~ 131.1）
                        (132, float('inf'), 'orange_data_export/tree.pkcls')  # 高價群組（tree: 88.8 ~ 165.2）
                    ]
                
                self.model_price_ranges = sorted(model_price_ranges, key=lambda x: x[0])
                self.model_available = False
                
                # 載入所有模型
                for min_price, max_price, model_path in self.model_price_ranges:
                    model_name = f"model_{min_price}_{max_price}"
                    try:
                        if os.path.exists(model_path):
                            loader = OrangeModelLoader(model_path)
                            self.model_loaders[model_name] = {
                                'loader': loader,
                                'min_price': min_price,
                                'max_price': max_price,
                                'path': model_path
                            }
                            self.model_available = True
                            print(f"[Orange] 成功載入模型 {model_name}: {model_path} (價格範圍: {min_price}-{max_price})")
                        else:
                            print(f"[Orange Warning] 模型文件不存在: {model_path}")
                    except Exception as e:
                        print(f"[Orange Warning] 載入模型 {model_name} 失敗: {e}")
                
                if not self.model_available:
                    self.load_error = "所有模型載入失敗"
                    print(f"[Orange Warning] 所有模型載入失敗")
                else:
                    print(f"[Orange] 成功載入 {len(self.model_loaders)} 個模型")
            else:
                # 單一模型模式（原有邏輯）
                if model_path is None:
                    model_path = 'orange_data_export/tree.pkcls'
                self.model_path = model_path
                
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
        
        # ==========================================
        # 【參數調整區】策略參數設定
        # ==========================================
        # 以下參數可直接修改以調整策略行為
        #
        # 1. 價格偏離閾值（第 90 行）【最重要參數】
        #    - 參數名：self.deviation_threshold_pct
        #    - 預設值：5.0（表示 5%）
        #    - 說明：當前價格與預測價格的偏差達到此百分比時進行交易
        #    - 調整建議：
        #      * 降低此值（如 3.0）→ 更頻繁交易，捕捉更多機會，但可能增加假訊號
        #      * 提高此值（如 7.0-10.0）→ 更保守，只在明顯偏離時交易，減少交易次數
        #    - 影響：直接影響交易頻率，是最重要的參數
        #    - 範例：設定為 3.0 時，價格低於預測 3% 即可買進；設定為 7.0 時需低於 7% 才買進
        self.deviation_threshold_pct = 5.0
        
        # 2. 穩定性計算回顧天數（第 91 行）
        #    - 參數名：self.stability_lookback_days
        #    - 預設值：7（使用最近 7 天的預測值計算波動率）
        #    - 說明：計算預測穩定性時使用的歷史預測天數
        #    - 調整建議：
        #      * 降低此值（如 5）→ 更敏感於近期波動，倉位調整更靈活
        #      * 提高此值（如 10-14）→ 更平滑的穩定性計算，倉位調整更穩定
        #    - 影響：影響倉位大小的計算，間接影響風險控制
        #    - 範例：設定為 5 時，只看最近 5 天的預測波動；設定為 14 時看最近 14 天
        self.stability_lookback_days = 7
        
        # 3. 允許全倉的最大波動率（第 92 行）
        #    - 參數名：self.max_volatility_for_full_position
        #    - 預設值：2.0（表示 2%）
        #    - 說明：當預測波動率低於此值時，使用 100% 倉位；超過此值則降低倉位
        #    - 調整建議：
        #      * 降低此值（如 1.5）→ 更保守，更容易降低倉位
        #      * 提高此值（如 3.0）→ 更積極，更容易使用全倉
        #    - 影響：影響倉位大小，間接影響風險和報酬
        #    - 注意：倉位會在 20%-100% 之間線性調整（見 _calculate_position_size 方法第 303-331 行）
        #    - 範例：設定為 1.5 時，波動率超過 1.5% 就開始降低倉位；設定為 3.0 時超過 3% 才降低
        self.max_volatility_for_full_position = 2.0
    
    def _select_model_by_price(self, current_price):
        """
        根據當前價格選擇合適的模型
        
        參數:
        - current_price: 當前股價
        
        返回:
        - loader: 選中的模型載入器，如果沒有合適的模型則返回 None
        - model_name: 模型名稱
        """
        if not self.use_multi_model:
            return self.model_loader, 'single_model'
        
        if not self.model_available or not self.model_loaders:
            return None, None
        
        # 根據價格範圍選擇模型
        for model_name, model_info in self.model_loaders.items():
            min_price = model_info['min_price']
            max_price = model_info['max_price']
            if min_price <= current_price < max_price:
                return model_info['loader'], model_name
        
        # 如果沒有找到合適的模型，返回 None
        return None, None
    
    def _predict_price(self, row):
        """
        使用 Orange 模型預測收盤價
        
        參數:
        - row: 當天的資料行（包含所有指標）
        
        返回:
        - dict: 包含預測結果和調試信息的字典
          {
            'predicted_price': float or None,  # 預測價格
            'prediction_status': str,  # 'success', 'model_unavailable', 'features_missing', 'prediction_error', 'no_model_for_price'
            'missing_features': list,  # 缺失的特徵列表
            'feature_values': dict,  # 特徵值字典
            'error_message': str or None  # 錯誤訊息（如果有）
            'selected_model': str or None  # 選中的模型名稱（多模型模式）
          }
        """
        result = {
            'predicted_price': None,
            'prediction_status': 'unknown',
            'missing_features': [],
            'feature_values': {},
            'error_message': None,
            'selected_model': None
        }
        
        if not self.model_available:
            result['prediction_status'] = 'model_unavailable'
            result['error_message'] = '模型不可用或未載入'
            return result
        
        # 獲取當前價格（用於選擇模型）
        current_price = None
        if 'close' in row and pd.notna(row['close']):
            current_price = float(row['close'])
        
        # 選擇模型
        if self.use_multi_model:
            if current_price is None:
                result['prediction_status'] = 'no_model_for_price'
                result['error_message'] = '無法獲取當前價格，無法選擇模型'
                return result
            
            selected_loader, model_name = self._select_model_by_price(current_price)
            if selected_loader is None:
                result['prediction_status'] = 'no_model_for_price'
                result['error_message'] = f'沒有適合價格 {current_price} 的模型'
                return result
            
            result['selected_model'] = model_name
            model_loader = selected_loader
        else:
            if self.model_loader is None:
                result['prediction_status'] = 'model_unavailable'
                result['error_message'] = '模型載入器不可用'
                return result
            model_loader = self.model_loader
        
        # 提取特徵
        feature_dict = {}
        missing_features = []
        for feature_name in self.feature_names:
            if feature_name in row:
                value = row[feature_name]
                # 檢查是否為有效數值
                if pd.notna(value):
                    feature_dict[feature_name] = float(value)
                else:
                    # 特徵缺失，無法預測
                    missing_features.append(f"{feature_name} (值為 NaN)")
            else:
                # 特徵不存在，無法預測
                missing_features.append(f"{feature_name} (欄位不存在)")
        
        result['missing_features'] = missing_features
        result['feature_values'] = feature_dict.copy()
        
        if missing_features:
            # 特徵缺失，無法預測
            result['prediction_status'] = 'features_missing'
            result['error_message'] = f"缺少特徵: {', '.join(missing_features)}"
            return result
        
        # 轉換為 DataFrame
        feature_df = pd.DataFrame([feature_dict])
        
        try:
            # 使用模型預測
            predicted_price = model_loader.predict(feature_df)[0]
            result['predicted_price'] = float(predicted_price)
            result['prediction_status'] = 'success'
            return result
        except Exception as e:
            # 預測失敗
            result['prediction_status'] = 'prediction_error'
            result['error_message'] = str(e)
            return result
    
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
        # 參數說明：max_volatility - 當波動率達到此值時使用最小倉位（20%）
        #           調整建議：可根據風險承受度調整（建議範圍：8.0-12.0）
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
        基於 Orange 預測的純均值回歸策略產生交易訂單
        
        策略邏輯：
        1. 使用 Orange 模型預測收盤價
        2. 計算當前價格與預測價格的偏離度
        3. 當偏離度超過閾值時進行交易（買進或賣出）
        4. 根據預測穩定性動態調整倉位大小
        
        交易條件：
        - 買進：當前價格 < 預測價格 × (1 - 閾值%) 且未持有
        - 賣出：當前價格 > 預測價格 × (1 + 閾值%) 且已持有
        
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
        prediction_result = self._predict_price(row)
        predicted_price = prediction_result.get('predicted_price')
        
        # 保存預測結果到狀態（包含調試信息）
        state['predicted_price'] = predicted_price
        state['prediction_debug'] = {
            'prediction_status': prediction_result.get('prediction_status'),
            'missing_features': prediction_result.get('missing_features', []),
            'feature_values': prediction_result.get('feature_values', {}),
            'error_message': prediction_result.get('error_message'),
            'selected_model': prediction_result.get('selected_model')  # 多模型模式下顯示選中的模型
        }
        
        if predicted_price is None:
            # 預測失敗，不執行交易
            return orders
        
        # 計算價格偏離度
        deviation = self._calculate_price_deviation(current_price, predicted_price)
        
        if deviation is None:
            return orders
        
        # 更新預測歷史（用於計算穩定性）
        if 'prediction_history' not in state:
            state['prediction_history'] = []
        prediction_history = state['prediction_history']
        prediction_history.append(predicted_price)
        # 只保留最近需要的天數
        if len(prediction_history) > self.stability_lookback_days:
            prediction_history = prediction_history[-self.stability_lookback_days:]
            state['prediction_history'] = prediction_history
        
        # 計算預測穩定性（用於風險調整）
        prediction_stability = self._calculate_prediction_stability(state)
        position_size = self._calculate_position_size(prediction_stability)
        
        # 檢查是否持有股票
        is_holding = state.get('state', False)
        
        # 買進條件：當前價格低於預測 >= 閾值 且未持有
        if deviation <= -self.deviation_threshold_pct and not is_holding:
            trade_step = self._create_trade_step('Orange均值回歸買進', [
                {'name': '預測價格', 'value': predicted_price},
                {'name': '當前價格', 'value': current_price},
                {'name': '價格偏離度(%)', 'value': deviation},
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
                'position_size': position_size
            })
            state['state'] = True
        
        # 賣出條件：當前價格高於預測 >= 閾值 且已持有
        elif deviation >= self.deviation_threshold_pct and is_holding:
            trade_step = self._create_trade_step('Orange均值回歸賣出', [
                {'name': '預測價格', 'value': predicted_price},
                {'name': '當前價格', 'value': current_price},
                {'name': '價格偏離度(%)', 'value': deviation},
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
                'position_size': position_size
            })
            state['state'] = False
        
        return orders
