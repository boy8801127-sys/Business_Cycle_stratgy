"""
查看 Orange 模型內容的腳本
用於檢查 tree.pkcls 文件的詳細信息
"""

import os
import sys
import pickle

# 設置環境變量以支持無頭模式
if 'QT_QPA_PLATFORM' not in os.environ:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'

try:
    import Orange
    from Orange.data import Table, Domain, ContinuousVariable
    ORANGE_AVAILABLE = True
except ImportError:
    ORANGE_AVAILABLE = False
    print("[錯誤] Orange 庫未安裝，請先安裝: pip install orange3")
    sys.exit(1)

def inspect_model(model_path='orange_data_export/tree.pkcls'):
    """檢查 Orange 模型的詳細信息"""
    
    if not os.path.exists(model_path):
        print(f"[錯誤] 模型文件不存在: {model_path}")
        return
    
    print("=" * 80)
    print("Orange 模型內容檢查")
    print("=" * 80)
    print(f"\n模型文件: {model_path}")
    
    try:
        # 載入模型
        print("\n[步驟 1] 載入模型...")
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        print(f"✓ 模型載入成功")
        print(f"  模型類型: {type(model).__name__}")
        print(f"  模型類別: {type(model).__module__}")
        
        # 檢查模型的基本屬性
        print("\n[步驟 2] 模型基本屬性:")
        if hasattr(model, 'name'):
            print(f"  名稱: {model.name}")
        if hasattr(model, 'params'):
            print(f"  參數: {model.params}")
        
        # 檢查 Domain（包含特徵和目標變量信息）
        print("\n[步驟 3] Domain 信息（特徵和目標變量）:")
        if hasattr(model, 'domain'):
            domain = model.domain
            print(f"  Domain 類型: {type(domain).__name__}")
            
            # 特徵（Attributes）
            if hasattr(domain, 'attributes') and domain.attributes:
                print(f"\n  特徵數量: {len(domain.attributes)}")
                print(f"  特徵列表:")
                for i, attr in enumerate(domain.attributes, 1):
                    print(f"    {i}. {attr.name}")
                    if hasattr(attr, 'number_of_decimals'):
                        print(f"       小數位數: {attr.number_of_decimals}")
            
            # 目標變量（Class Variable）
            if hasattr(domain, 'class_var') and domain.class_var:
                class_var = domain.class_var
                print(f"\n  目標變量:")
                print(f"    名稱: {class_var.name}")
                print(f"    類型: {type(class_var).__name__}")
                if hasattr(class_var, 'number_of_decimals'):
                    print(f"    小數位數: {class_var.number_of_decimals}")
            elif hasattr(domain, 'class_vars') and domain.class_vars:
                print(f"\n  目標變量數量: {len(domain.class_vars)}")
                for i, class_var in enumerate(domain.class_vars, 1):
                    print(f"    {i}. {class_var.name}")
            else:
                print(f"\n  目標變量: 無（可能是無監督模型）")
        else:
            print("  ✗ 模型沒有 domain 屬性")
        
        # 如果是樹模型，顯示樹的結構
        print("\n[步驟 4] 樹模型結構:")
        if hasattr(model, 'tree'):
            tree = model.tree
            print(f"  樹類型: {type(tree).__name__}")
            
            # 顯示樹的統計信息
            if hasattr(tree, 'size'):
                print(f"  節點數量: {tree.size()}")
            if hasattr(tree, 'height'):
                print(f"  樹高度: {tree.height()}")
            
            # 顯示前幾個節點的信息（如果有）
            if hasattr(tree, 'children'):
                print(f"  根節點子節點數: {len(tree.children) if tree.children else 0}")
        elif 'tree' in type(model).__name__.lower():
            print(f"  這是樹模型，但結構信息可能需要特殊方法訪問")
        
        # 嘗試顯示模型的可視化結構（文字版）
        print("\n[步驟 5] 模型規則（前10條，如果可用）:")
        try:
            # 對於決策樹，嘗試打印一些規則
            if hasattr(model, 'to_string'):
                rules = model.to_string()
                # 只顯示前2000個字符
                print(rules[:2000])
                if len(rules) > 2000:
                    print(f"\n  ... (還有 {len(rules) - 2000} 個字符未顯示)")
        except Exception as e:
            print(f"  無法顯示規則: {e}")
        
        # 測試預測功能
        print("\n[步驟 6] 測試預測功能:")
        try:
            # 建立測試數據（使用模型的 domain）
            if hasattr(model, 'domain') and model.domain and model.domain.attributes:
                # 創建一個只包含特徵的 domain（預測用）
                from Orange.data import Domain as OrangeDomain
                pred_domain = OrangeDomain(model.domain.attributes)
                
                # 生成測試數據（使用第一個特徵的平均值或默認值）
                import numpy as np
                test_data = np.array([[85.0, 900.0, 43000.0]])  # 默認測試值
                
                # 調整數據維度以匹配特徵數量
                n_features = len(model.domain.attributes)
                if test_data.shape[1] != n_features:
                    # 如果特徵數量不匹配，使用隨機值
                    test_data = np.random.rand(1, n_features) * 100
                    print(f"  使用隨機測試數據（特徵數量: {n_features}）")
                else:
                    print(f"  使用測試數據（特徵數量: {n_features}）")
                
                # 創建 Orange Table
                test_table = Table.from_numpy(pred_domain, test_data)
                
                # 進行預測
                predictions = model(test_table)
                
                if isinstance(predictions, Table):
                    pred_values = predictions.Y.flatten()
                else:
                    pred_values = np.array(predictions).flatten()
                
                print(f"  ✓ 預測成功")
                print(f"  預測結果: {pred_values[0]:.2f}")
                print(f"  預測結果類型: {type(pred_values[0])}")
            else:
                print("  ✗ 無法測試預測（缺少 domain 信息）")
        except Exception as e:
            print(f"  ✗ 預測測試失敗: {e}")
            import traceback
            traceback.print_exc()
        
        # 顯示所有可用的屬性和方法
        print("\n[步驟 7] 模型可用屬性和方法:")
        attrs = [attr for attr in dir(model) if not attr.startswith('_')]
        print(f"  屬性/方法總數: {len(attrs)}")
        print(f"  前20個: {', '.join(attrs[:20])}")
        if len(attrs) > 20:
            print(f"  ... (還有 {len(attrs) - 20} 個)")
        
        print("\n" + "=" * 80)
        print("檢查完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[錯誤] 檢查模型時發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    inspect_model()


