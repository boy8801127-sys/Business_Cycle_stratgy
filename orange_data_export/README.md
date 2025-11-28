# Orange 資料導出說明

本資料夾包含用於 Orange 預測分析的資料導出腳本。

## 檔案說明

- **export_for_prediction.py**: 資料導出腳本，從資料庫讀取資料並匯出為 CSV 供 Orange 使用

## 快速開始

### 1. 執行資料導出

```bash
cd D:\Business_Cycle_stratgy
python orange_data_export/export_for_prediction.py
```

預設會產生 `prediction_data.csv` 檔案在 `orange_data_export/` 資料夾中。

### 2. 自訂參數

```bash
# 指定日期範圍
python orange_data_export/export_for_prediction.py --start-date 20200101 --end-date 20241231

# 指定預測未來天數
python orange_data_export/export_for_prediction.py --future-days 10

# 指定輸出檔案路徑
python orange_data_export/export_for_prediction.py --output my_prediction_data.csv
```

### 3. 查看完整參數說明

```bash
python orange_data_export/export_for_prediction.py --help
```

## Orange 工作流程建立

由於 Orange 工作流程檔案（.ows）是複雜的 XML 格式，建議您：

1. **開啟 Orange**
2. **按照 [Orange 預測指引](../docs/ORANGE_PREDICTION_GUIDE.md) 的說明手動建立工作流程**

或者：

1. **在 Orange 中建立基本工作流程後**
2. **儲存為 `.ows` 檔案**
3. **之後可以重複載入使用**

## 基本工作流程步驟

1. **File** 節點 → 載入 `prediction_data.csv`
2. **Select Columns** 節點 → 選擇特徵和目標變數
3. **Impute** 節點 → 處理缺失值
4. **Data Sampler** 節點 → 分割訓練集和測試集（80/20）
5. **模型節點**（例如：Random Forest, Linear Regression）
6. **Predictions** 節點 → 產生預測
7. **Regression Evaluation** 節點 → 評估模型

詳細說明請參考 [Orange 預測指引](../docs/ORANGE_PREDICTION_GUIDE.md)。

## 資料欄位說明

導出的 CSV 檔案包含以下欄位：

### 目標變數
- `future_return_5d`: 未來 5 天報酬率（%）- 迴歸問題目標
- `future_direction_5d`: 未來 5 天漲跌方向（1=上漲，0=下跌）- 分類問題目標

### 景氣燈號特徵
- `cycle_score`: 當月景氣對策信號綜合分數
- `signal_encoded`: 燈號編碼（1-5）
- `score_lag1/2/3`: 前 1/2/3 個月的分數
- `score_change`: 分數變化
- `score_change_pct`: 分數變化百分比

### 技術指標特徵
- `ma5/20/60`: 移動平均線
- `price_vs_ma5/20`: 股價相對位置
- `volatility_20`: 波動率
- `return_1d/5d/20d`: 過去報酬率
- `rsi`: RSI 指標

詳細欄位說明請參考 [Orange 預測指引](../docs/ORANGE_PREDICTION_GUIDE.md)。

## 注意事項

1. 確保資料庫中有足夠的資料（建議至少 1-2 年的資料）
2. 預測未來天數越長，預測難度越高
3. 建議先嘗試預測短期（5-10 天），再嘗試長期（20-30 天）
4. 定期更新資料以保持模型的準確性

## 疑難排解

### 問題：找不到資料庫檔案

**解決方案**：確認資料庫路徑是否正確，或使用 `--db-path` 參數指定正確路徑：
```bash
python orange_data_export/export_for_prediction.py --db-path "D:\your_path\taiwan_stock_all_data.db"
```

### 問題：匯出的資料筆數太少

**解決方案**：
- 確認資料庫中有足夠的資料
- 檢查日期範圍設定是否正確
- 確認股票代號是否正確（預設為 006208）

### 問題：Orange 無法讀取 CSV 檔案

**解決方案**：
- 確認 CSV 檔案編碼為 UTF-8
- 檢查檔案路徑中是否有特殊字元
- 嘗試用 Excel 開啟 CSV 確認格式正確

