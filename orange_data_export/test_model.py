"""
[Orange 相關功能] Orange 模型測試腳本

測試 Orange 模型是否可以正常載入和預測
"""

import os
import sys
import pandas as pd

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtesting.orange_model_loader import OrangeModelLoader


def test_model_loading():
    """測試模型載入"""
    print("=" * 60)
    print("Orange 模型載入測試")
    print("=" * 60)
    
    model_path = 'orange_data_export/tree.pkcls'
    
    if not os.path.exists(model_path):
        print(f"[Error] 模型文件不存在: {model_path}")
        return False
    
    try:
        print(f"\n[步驟 1] 載入模型: {model_path}")
        loader = OrangeModelLoader(model_path)
        print("[Success] 模型載入成功")
        
        # 顯示模型資訊
        feature_names = loader.get_feature_names()
        if feature_names:
            print(f"\n[Info] 模型使用的特徵:")
            for i, name in enumerate(feature_names, 1):
                print(f"  {i}. {name}")
        else:
            print("\n[Warning] 無法取得模型特徵名稱")
        
        return True
        
    except ImportError as e:
        print(f"[Error] Orange 庫未安裝: {e}")
        return False
    except Exception as e:
        print(f"[Error] 模型載入失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prediction():
    """測試模型預測"""
    print("\n" + "=" * 60)
    print("Orange 模型預測測試")
    print("=" * 60)
    
    model_path = 'orange_data_export/tree.pkcls'
    csv_path = 'results/orange_analysis_data.csv'
    
    if not os.path.exists(model_path):
        print(f"[Error] 模型文件不存在: {model_path}")
        return False
    
    if not os.path.exists(csv_path):
        print(f"[Error] CSV 文件不存在: {csv_path}")
        return False
    
    try:
        # 載入模型
        print(f"\n[步驟 1] 載入模型: {model_path}")
        loader = OrangeModelLoader(model_path)
        
        # 讀取 CSV 數據
        print(f"\n[步驟 2] 讀取 CSV 數據: {csv_path}")
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        print(f"[Info] 成功讀取 {len(df)} 筆數據")
        
        # 確認需要的 3 個特徵存在
        required_features = [
            'signal_領先指標綜合指數',
            'coincident_海關出口值(十億元)',
            'lagging_全體金融機構放款與投資(10億元)'
        ]
        
        missing_features = [f for f in required_features if f not in df.columns]
        if missing_features:
            print(f"[Error] CSV 中缺少以下特徵: {missing_features}")
            return False
        
        print(f"\n[步驟 3] 提取特徵數據")
        # 選擇前 5 筆有效數據進行測試
        test_df = df[required_features].dropna().head(5)
        
        if test_df.empty:
            print("[Error] 沒有有效的測試數據（所有數據都包含缺失值）")
            return False
        
        print(f"[Info] 準備測試 {len(test_df)} 筆數據")
        
        # 進行預測
        print(f"\n[步驟 4] 進行預測")
        predictions = loader.predict(test_df)
        
        print(f"\n[Success] 預測完成！")
        print(f"\n預測結果:")
        print("-" * 60)
        for i, (idx, row) in enumerate(test_df.iterrows(), 1):
            pred_value = predictions[i-1] if i <= len(predictions) else None
            print(f"\n測試數據 {i}:")
            print(f"  領先指標綜合指數: {row['signal_領先指標綜合指數']:.2f}")
            print(f"  海關出口值: {row['coincident_海關出口值(十億元)']:.2f}")
            print(f"  全體金融機構放款與投資: {row['lagging_全體金融機構放款與投資(10億元)']:.2f}")
            if pred_value is not None:
                print(f"  預測收盤價: {pred_value:.2f}")
            else:
                print(f"  預測收盤價: N/A")
        
        print("\n" + "=" * 60)
        print("測試完成！")
        print("=" * 60)
        
        return True
        
    except ImportError as e:
        print(f"[Error] Orange 庫未安裝: {e}")
        return False
    except Exception as e:
        print(f"[Error] 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主測試函數"""
    print("\n" + "=" * 60)
    print("Orange 模型測試腳本")
    print("=" * 60)
    
    # 測試 1: 模型載入
    load_success = test_model_loading()
    
    if not load_success:
        print("\n[Error] 模型載入失敗，無法繼續測試")
        return
    
    # 測試 2: 模型預測
    pred_success = test_prediction()
    
    if pred_success:
        print("\n[Success] 所有測試通過！")
    else:
        print("\n[Warning] 預測測試失敗")


if __name__ == '__main__':
    main()
