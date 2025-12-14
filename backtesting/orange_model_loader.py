"""
[Orange 相關功能] 此檔案僅用於載入 Orange 機器學習模型

Orange 模型載入器
用於載入 Orange 訓練的 .pkcls 模型並進行預測
"""

import os
import sys
import pandas as pd
import numpy as np
import pickle
import warnings

# 設置環境變量以支持無頭模式（在導入 Orange 之前）
# 這可以避免 PyQt GUI 依賴問題
if 'QT_QPA_PLATFORM' not in os.environ:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# 嘗試匯入 Orange 庫（可選依賴）
try:
    import Orange
    from Orange.data import Table, Domain, ContinuousVariable
    # 抑制 Orange 的 deprecation warnings
    try:
        from Orange.utils import OrangeDeprecationWarning
        warnings.filterwarnings('ignore', category=OrangeDeprecationWarning)
    except (ImportError, AttributeError):
        # 如果無法導入警告類別，使用通用方式抑制
        warnings.filterwarnings('ignore', message='.*Domain.__bool__.*')
    ORANGE_AVAILABLE = True
except ImportError:
    ORANGE_AVAILABLE = False
    Orange = None
    Table = None
    Domain = None
    ContinuousVariable = None


class OrangeModelLoader:
    """
    [Orange 相關功能] Orange 模型載入器
    
    用於載入 Orange 訓練的 .pkcls 格式模型並進行預測
    如果 Orange 庫未安裝，初始化會拋出 ImportError
    """
    
    def __init__(self, model_path):
        """
        初始化模型載入器
        
        參數:
        - model_path: Orange 模型文件路徑（.pkcls）
        
        異常:
        - ImportError: 如果 Orange 庫未安裝
        - FileNotFoundError: 如果模型文件不存在
        - RuntimeError: 如果模型載入失敗
        """
        if not ORANGE_AVAILABLE:
            raise ImportError(
                "Orange 庫未安裝，無法載入 Orange 模型。\n"
                "請先安裝: pip install orange3"
            )
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        
        self.model_path = model_path
        self.model = None
        self.domain = None
        self.feature_names = None
        
        # 載入模型
        self._load_model()
    
    def _load_model(self):
        """載入 Orange 模型"""
        # 設置環境變量以支持無頭模式（避免 PyQt GUI 依賴）
        original_qt_platform = os.environ.get('QT_QPA_PLATFORM')
        try:
            # 嘗試設置無頭模式
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        except:
            pass
        
        try:
            # 載入 Orange 模型（.pkcls 文件實際上是 pickle 格式）
            # 注意：某些 Orange 模型可能需要 PyQt，即使設置了無頭模式
            # 如果遇到 ImportError，可能需要安裝 PyQt5: pip install PyQt5
            try:
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
            except ImportError as import_err:
                # 如果是 PyQt 相關的 ImportError，提供更清晰的錯誤訊息
                error_msg = str(import_err)
                if 'PyQt' in error_msg or 'PySide' in error_msg:
                    raise RuntimeError(
                        f"載入 Orange 模型需要 GUI 依賴庫。\n"
                        f"錯誤詳情: {error_msg}\n"
                        f"解決方案: 請安裝 PyQt5: pip install PyQt5\n"
                        f"或者使用無頭模式: 設置環境變量 QT_QPA_PLATFORM=offscreen"
                    )
                else:
                    raise
            
            # 取得模型的 domain（包含特徵名稱）
            if hasattr(self.model, 'domain'):
                self.domain = self.model.domain
                # 提取特徵名稱
                self.feature_names = [attr.name for attr in self.domain.attributes]
                print(f"[Orange] 成功載入 Orange 模型")
                print(f"[Orange] 模型特徵數量: {len(self.feature_names)}")
                print(f"[Orange] 特徵名稱: {self.feature_names}")
            else:
                print("[Orange Warning] 模型沒有 domain 資訊，需要手動指定特徵名稱")
                self.feature_names = None
                
        except Exception as e:
            raise RuntimeError(f"載入 Orange 模型失敗: {e}")
        finally:
            # 恢復原始環境變量
            if original_qt_platform is None:
                os.environ.pop('QT_QPA_PLATFORM', None)
            else:
                os.environ['QT_QPA_PLATFORM'] = original_qt_platform
    
    def predict(self, data):
        """
        使用模型進行預測
        
        參數:
        - data: 輸入數據，可以是：
           1. pandas DataFrame（包含特徵欄位）
           2. numpy array（形狀為 [n_samples, n_features]）
           3. dict（鍵為特徵名稱，值為數值）
        
        返回:
        - 預測值（numpy array）
        
        異常:
        - RuntimeError: 如果模型未載入或預測失敗
        """
        if self.model is None:
            raise RuntimeError("模型未載入")
        
        # 轉換輸入數據為 Orange Table
        orange_table = self._convert_to_orange_table(data)
        
        # 進行預測
        try:
            predictions = self.model(orange_table)
            # 轉換為 numpy array
            if isinstance(predictions, Table):
                pred_values = predictions.Y.flatten()
            else:
                pred_values = np.array(predictions).flatten()
            
            return pred_values
        except Exception as e:
            raise RuntimeError(f"Orange 模型預測失敗: {e}")
    
    def _convert_to_orange_table(self, data):
        """
        將輸入數據轉換為 Orange Table
        
        參數:
        - data: 輸入數據
        
        返回:
        - Orange Table 對象
        
        異常:
        - ValueError: 如果特徵缺失或數據格式不正確
        - TypeError: 如果數據類型不支援
        """
        # 如果輸入是 dict，轉換為 DataFrame
        if isinstance(data, dict):
            data = pd.DataFrame([data])
        
        # 如果輸入是 DataFrame，提取特徵
        if isinstance(data, pd.DataFrame):
            # 確保所有特徵都存在
            if self.feature_names:
                missing_features = [f for f in self.feature_names if f not in data.columns]
                if missing_features:
                    raise ValueError(f"缺少 Orange 模型需要的特徵: {missing_features}")
                feature_data = data[self.feature_names].values
            else:
                # 如果沒有特徵名稱，使用所有數值欄位
                feature_data = data.select_dtypes(include=[np.number]).values
        elif isinstance(data, np.ndarray):
            feature_data = data
        else:
            raise TypeError(f"不支援的數據類型: {type(data)}")
        
        # 檢查是否有缺失值
        if np.isnan(feature_data).any():
            raise ValueError("輸入數據包含缺失值（NaN），無法進行預測")
        
        # 建立 Orange Domain
        # 預測時只需要 attributes（特徵），不需要 class variable（目標變量）
        if self.domain is not None:
            # 使用模型的 domain，但只保留 attributes（不包含 class_var）
            # 這對於預測是正確的，因為我們只提供特徵，不提供目標值
            domain = Domain(self.domain.attributes)
        else:
            # 手動建立 domain
            attributes = [ContinuousVariable(f"feature_{i}") for i in range(feature_data.shape[1])]
            domain = Domain(attributes)
        
        # 建立 Orange Table
        orange_table = Table.from_numpy(domain, feature_data)
        
        return orange_table
    
    def get_feature_names(self):
        """
        取得模型使用的特徵名稱
        
        返回:
        - 特徵名稱列表（如果可用）
        """
        return self.feature_names


# 使用範例（僅供測試）
if __name__ == '__main__':
    # 測試載入模型
    model_path = 'orange_data_export/tree.pkcls'
    
    try:
        loader = OrangeModelLoader(model_path)
        
        # 建立測試數據（使用 Orange 分析發現的 3 個特徵）
        test_data = pd.DataFrame({
            'signal_領先指標綜合指數': [85.0],
            'coincident_海關出口值(十億元)': [900.0],
            'lagging_全體金融機構放款與投資(10億元)': [43000.0]
        })
        
        # 進行預測
        predictions = loader.predict(test_data)
        print(f"\n預測結果: {predictions}")
        
    except Exception as e:
        print(f"錯誤: {e}")
