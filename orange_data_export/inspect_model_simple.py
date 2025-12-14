"""
簡單的模型檢查腳本（不需要 Orange 庫也能查看基本結構）
"""

import os
import sys
import pickle

def inspect_model_simple(model_path='orange_data_export/tree.pkcls'):
    """簡單檢查模型文件內容"""
    
    if not os.path.exists(model_path):
        print(f"[錯誤] 模型文件不存在: {model_path}")
        return
    
    print("=" * 80)
    print("模型文件基本信息")
    print("=" * 80)
    print(f"\n模型文件: {model_path}")
    file_size = os.path.getsize(model_path)
    print(f"文件大小: {file_size} 字節 ({file_size/1024:.2f} KB)")
    
    try:
        print("\n[步驟 1] 嘗試載入 pickle 文件...")
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        print(f"✓ 成功載入")
        print(f"  對象類型: {type(model).__name__}")
        print(f"  模組路徑: {type(model).__module__}")
        print(f"  類名: {type(model)}")
        
        # 顯示對象的所有屬性
        print("\n[步驟 2] 對象屬性:")
        attrs = [attr for attr in dir(model) if not attr.startswith('__')]
        print(f"  屬性/方法總數: {len(attrs)}")
        print(f"  屬性列表:")
        for attr in attrs[:30]:  # 只顯示前30個
            try:
                value = getattr(model, attr)
                if not callable(value):
                    # 只顯示非函數的屬性值
                    if isinstance(value, (str, int, float, bool, type(None))):
                        print(f"    {attr} = {value}")
                    elif isinstance(value, (list, tuple)):
                        print(f"    {attr} = {type(value).__name__}[{len(value)}]")
                        if len(value) > 0 and len(value) <= 5:
                            print(f"        內容: {value}")
                    else:
                        print(f"    {attr} = {type(value).__name__}")
            except:
                print(f"    {attr} = (無法訪問)")
        
        if len(attrs) > 30:
            print(f"    ... (還有 {len(attrs) - 30} 個屬性未顯示)")
        
        # 特別檢查 domain
        print("\n[步驟 3] 檢查 Domain 相關屬性:")
        domain_attrs = ['domain', 'Domain', 'class_var', 'attributes', 'features']
        for attr_name in domain_attrs:
            if hasattr(model, attr_name):
                value = getattr(model, attr_name)
                print(f"  {attr_name}: {type(value).__name__}")
                if value is not None:
                    if hasattr(value, '__len__'):
                        try:
                            print(f"    長度: {len(value)}")
                        except:
                            pass
                    if hasattr(value, '__iter__') and not isinstance(value, str):
                        try:
                            items = list(value)[:5]
                            print(f"    前幾項: {items}")
                        except:
                            pass
        
        # 檢查是否有 tree 屬性
        print("\n[步驟 4] 檢查樹結構:")
        if hasattr(model, 'tree'):
            tree = model.tree
            print(f"  tree 類型: {type(tree).__name__}")
            if hasattr(tree, 'size'):
                try:
                    print(f"  節點數量: {tree.size()}")
                except:
                    pass
        
        print("\n" + "=" * 80)
        print("檢查完成")
        print("=" * 80)
        print("\n提示: 如需查看完整的 Orange 模型信息（包括特徵名稱、Domain 等），")
        print("請確保已安裝 Orange 庫 (pip install orange3)，然後運行:")
        print("  python orange_data_export/inspect_model.py")
        
    except Exception as e:
        print(f"\n[錯誤] 載入文件時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        print("\n提示: 這可能是因為:")
        print("  1. 文件格式不正確")
        print("  2. 缺少必要的依賴庫（如 Orange）")
        print("  3. 文件損壞")

if __name__ == '__main__':
    inspect_model_simple()


