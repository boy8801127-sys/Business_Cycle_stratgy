# Orange 模型整合說明

## 概述

此目錄包含 Orange 機器學習模型的相關檔案和功能。Orange 相關功能已與原有系統完全隔離，不會影響原有策略的運作。

## 檔案說明

- `tree.pkcls`: Orange 訓練的決策樹模型（使用 3 個特徵預測收盤價）
- `test_model.py`: 測試腳本，用於驗證模型是否可以正常載入和預測

## 使用方式

### 1. 測試模型載入

```bash
python orange_data_export/test_model.py
```

此腳本會：
- 載入 `tree.pkcls` 模型
- 從 `results/orange_analysis_data.csv` 讀取測試數據
- 使用 3 個特徵進行預測
- 顯示預測結果

### 2. 在回測中使用

1. 執行 `python main.py`
2. 選擇選項 12（執行回測 - 新系統）
3. 選擇策略 2（Orange 預測策略）

## 模型使用的特徵

模型使用以下 3 個特徵進行預測：

1. `signal_領先指標綜合指數`
2. `coincident_海關出口值(十億元)`
3. `lagging_全體金融機構放款與投資(10億元)`

## 依賴套件

需要安裝 Orange 庫：

```bash
pip install orange3
```

**注意：** Orange 庫為可選依賴。如果未安裝，Orange 預測策略會自動回退到景氣燈號邏輯，不影響其他策略。

## 隔離措施

為了防止與原有系統混淆，所有 Orange 相關功能都採用了以下隔離措施：

1. **檔案命名：** 所有 Orange 相關檔案使用 `orange_` 前綴
2. **類別命名：** 所有 Orange 相關類別包含 `Orange` 關鍵字
3. **可選依賴：** Orange 庫為可選依賴，未安裝時不影響系統
4. **錯誤處理：** 所有 Orange 相關錯誤都被捕獲，確保系統穩定性
5. **降級機制：** 如果 Orange 功能不可用，策略自動回退到原始邏輯

## 注意事項

- 模型檔案（`.pkcls`）是 Orange 專用格式，無法用 scikit-learn 載入
- 特徵名稱必須與 CSV 檔案中的欄位名稱完全一致
- 如果特徵有缺失值，預測會自動跳過，使用備用邏輯
