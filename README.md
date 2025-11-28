# 景氣週期投資策略系統

## 專案簡介

本專案實作基於景氣燈號的資產輪動量化交易策略，參考 TEJ 台灣經濟新報的策略概念，使用公開資料來源進行回測。

策略邏輯：
- **景氣低迷（藍燈，SCORE ≤ 16）**：買進股票（006208，富邦台50），賣出避險資產
- **景氣過熱（紅燈，SCORE ≥ 38）**：賣出股票（006208），買進避險資產
- **景氣穩定（16 < SCORE < 38）**：首次進入時買進股票（006208）

## 系統架構

```
Business_Cycle_stratgy/
├── data_collection/          # 資料蒐集模組
│   ├── __init__.py
│   ├── cycle_data_collector.py    # 景氣燈號資料讀取（從 CSV，月轉日）
│   ├── stock_data_collector.py    # 股票和ETF資料蒐集（證交所 API）
│   └── database_manager.py        # 資料庫管理
├── backtesting/              # 回測模組
│   ├── __init__.py
│   ├── backtest_engine.py        # 自訂回測引擎
│   └── strategy.py               # 策略邏輯實作
├── business_cycle/           # 景氣燈號資料（已存在）
│   └── 景氣指標與燈號.csv         # 主要資料檔
├── config/                   # 設定檔
│   └── config.ini.example       # 設定檔範例
├── data_validation/          # 資料驗證模組
│   └── price_validator.py       # 股價資料驗證與修正
├── docs/                     # 文件資料夾
│   ├── GITHUB_SETUP.md          # GitHub 上傳指引
│   ├── POWER_BI_SETUP.md        # Power BI 連接指引
│   ├── DATABASE_SCHEMA.md       # 資料庫結構說明
│   └── ORANGE_PREDICTION_GUIDE.md # Orange 預測指引
├── orange_data_export/       # Orange 預測資料導出
│   └── export_for_prediction.py # 資料導出腳本
├── main.py                   # 主執行檔
├── README.md                 # 專案說明文件
├── requirements.txt          # 依賴套件
└── .gitignore               # Git 忽略檔案設定
```

## 快速開始

### 1. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 2. 設定資料庫路徑

資料庫預設路徑：`D:\all_data\taiwan_stock_all_data.db`

如果資料庫位置不同，請修改 `data_collection/database_manager.py` 中的預設路徑。

### 3. 執行主程式

```bash
python main.py
```

## 功能說明

### 選項 1：讀取景氣燈號資料

從 CSV 檔案讀取景氣指標資料，將月資料轉換為交易日資料。

- 資料來源：`business_cycle/景氣指標與燈號.csv`
- 處理日期範圍：2015-01-01 至今（可自訂）
- 功能：月資料轉換為交易日資料，計算 `val_shifted`（前一日數值）

### 選項 2：蒐集股票和ETF資料

從證交所 API 取得所有股票和ETF的股價資料。

- 資料來源：證交所公開 API（`MI_INDEX`）
- 包含：所有個股和 ETF（移除 ETF 過濾條件）
- 禮貌休息機制：每個請求之間休息 3-5 秒
- 重試機制：失敗時重試 3 次，每次間隔 5 秒

### 選項 3：執行回測

執行景氣週期投資策略回測。

支援的策略：
1. **短天期美債避險（00865B）**：使用短天期美債 ETF 作為避險資產
2. **現金避險**：使用現金作為避險資產（賣出股票後持有現金）
3. **長天期美債避險（00687B）**：使用長天期美債 ETF 作為避險資產
4. **反向ETF避險（00664R）**：使用 0050 反向 ETF 作為避險資產
5. **50:50配置（0050 + 短債）**：景氣過熱時保留 50% 股票，50% 避險資產

回測參數：
- 起始日期：預設 2015-01-01
- 結束日期：預設今天
- 初始資金：預設 100,000 元

### 選項 4：產生績效報告和圖表

產生回測績效報告和圖表（後續版本實作）。

### 選項 5：批次更新資料

批次更新股票和ETF資料，支援指定天數。

## 策略邏輯詳細說明

### 景氣燈號分數判斷

- **SCORE ≤ 16（藍燈）**：景氣低迷
  - 動作：買進 006208（富邦台50，100%），賣出避險資產（如果有）

- **SCORE ≥ 38（紅燈）**：景氣過熱
  - 動作：賣出 006208（100%），買進避險資產（如果有）
  - 例外：50:50 策略保留 50% 股票

- **16 < SCORE < 38（綠燈/黃藍燈/黃紅燈）**：景氣穩定
  - 動作：首次進入時買進 006208（100%）

### 資料處理

- 景氣燈號為月資料（YYYYMM），需轉換為交易日資料
- 每個月的每一天使用該月的景氣對策信號綜合分數
- 使用 `val_shifted`（前一日數值）進行策略判斷（參考原範例）

## 資料來源

### 景氣燈號資料

- 來源：政府開放資料（CSV 檔案）
- 檔案：`business_cycle/景氣指標與燈號.csv`
- 欄位：
  - `Date`：日期（YYYYMM 格式）
  - `景氣對策信號綜合分數`：景氣燈號分數（SCORE）
  - `景氣對策信號`：燈號顏色（藍、黃藍、綠、黃紅、紅）

### 股價資料

- 來源：證交所公開 API
- API：`MI_INDEX`（每日收盤行情）
- 包含：所有個股和 ETF、上櫃股票
- 儲存：SQLite 資料庫
  - `tw_stock_price_data`：上市股票和ETF資料
  - `tw_otc_stock_price_data`：上櫃股票資料
  - `tw_price_indices_data`：價格指數資料
  - `tw_return_indices_data`：報酬指數資料
  - `business_cycle_data`：景氣燈號資料

## 回測框架特點

- **簡化設計**：不依賴 Zipline，更易理解和修改
- **交易成本**：考慮手續費（0.1425%）和證交稅（0.3%）
- **最小交易單位**：以千股為單位（符合台灣市場）
- **績效指標**：計算總報酬率、年化報酬率、夏普比率、最大回落等

## 注意事項

1. **資料庫路徑**：預設使用 `D:\all_data\taiwan_stock_all_data.db`，請確保資料庫存在或有寫入權限

2. **禮貌休息**：API 請求之間會自動休息 3-5 秒，避免觸發速率限制

3. **資料完整性**：執行回測前請確保：
   - 景氣燈號資料已讀取
   - 股票和ETF資料已蒐集（包含 006208、00865B、00687B、00664R）

4. **ETF 上市日期**：
   - 00865B（短天期美債）：需確認上市日期
   - 00687B（長天期美債）：需確認上市日期
   - 00664R（0050反向）：需確認上市日期
   - 回測時會自動處理資料缺失的情況

## 依賴套件

- `pandas` >= 2.0.0：資料處理
- `numpy` >= 1.24.0：數值計算
- `requests` >= 2.31.0：HTTP 請求
- `matplotlib` >= 3.7.0：圖表繪製
- `plotly` >= 5.0.0：互動式圖表
- `pandas_market_calendars` >= 5.0.0：交易日曆

## 資料庫結構

本專案使用 SQLite 資料庫儲存所有資料，詳細資料表結構請參考 [資料庫結構說明文件](docs/DATABASE_SCHEMA.md)。

主要資料表包括：
- **tw_stock_price_data**：上市股票和ETF每日股價資料
- **tw_otc_stock_price_data**：上櫃股票每日股價資料
- **tw_price_indices_data**：價格指數資料
- **tw_return_indices_data**：報酬指數資料
- **business_cycle_data**：景氣燈號每日資料（從月資料轉換）

## 部署與設定

### 資料庫設定

資料庫檔案（`.db`）**不會**包含在 Git 倉庫中，請自行保管資料庫檔案。

預設資料庫路徑：`D:\all_data\taiwan_stock_all_data.db`

如需修改資料庫路徑，請編輯 `data_collection/database_manager.py` 中的 `__init__` 方法。

### 環境設定

1. 安裝 Python 依賴套件：
```bash
pip install -r requirements.txt
```

2. 設定資料庫路徑（如需要）

3. 準備景氣燈號資料（已包含在 `business_cycle/` 資料夾）

## 其他功能

### 資料驗證與修正

系統提供多種資料驗證與修正功能（選項 6-9）：
- 股價異常檢測
- 資料完整性檢查
- 零值價格填補
- 零股交易標註

詳細說明請參考主選單或執行 `python main.py` 查看。

### 資料分析工具

- **Power BI 連接**：請參考 [Power BI 連接指引](docs/POWER_BI_SETUP.md)
- **Orange 預測分析**：請參考 [Orange 預測指引](docs/ORANGE_PREDICTION_GUIDE.md)

## GitHub 上傳指引

如果您想將此專案上傳到 GitHub，請參考 [GitHub 上傳指引文件](docs/GITHUB_SETUP.md)。

**重要提醒**：
- 資料庫檔案（`.db`）已設定為不上傳（見 `.gitignore`）
- 請確保資料庫檔案安全保管
- 建議在 README 中說明如何設定資料庫路徑

## 授權

本專案僅供學習和研究使用。

## 參考資料

- TEJ 台灣經濟新報：從景氣燈號到資產輪動：一套避開熊市的量化策略
- 證交所公開資料 API
- 櫃買中心公開資料 API

