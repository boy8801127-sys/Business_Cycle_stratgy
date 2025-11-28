# 資料庫結構說明

本文件說明專案使用的 SQLite 資料庫（`taiwan_stock_all_data.db`）的所有資料表結構。

## 資料庫位置

預設路徑：`D:\all_data\taiwan_stock_all_data.db`

## 資料表列表

1. [tw_stock_price_data](#1-tw_stock_price_data) - 上市股票和ETF股價資料
2. [tw_otc_stock_price_data](#2-tw_otc_stock_price_data) - 上櫃股票股價資料
3. [tw_price_indices_data](#3-tw_price_indices_data) - 價格指數資料
4. [tw_return_indices_data](#4-tw_return_indices_data) - 報酬指數資料
5. [business_cycle_data](#5-business_cycle_data) - 景氣燈號資料

---

## 1. tw_stock_price_data

**說明**：儲存上市股票和ETF的每日股價資料，資料來源為證交所 API。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式） | 20250101 |
| stock_name | TEXT | 股票名稱 | 富邦台50 |
| ticker | TEXT | 股票代號（主鍵） | 006208 |
| open | REAL | 開盤價 | 45.50 |
| high | REAL | 最高價 | 46.00 |
| low | REAL | 最低價 | 45.20 |
| close | REAL | 收盤價 | 45.80 |
| volume | INTEGER | 成交量（股數） | 1000000 |
| turnover | REAL | 成交金額（元） | 45800000 |
| change | REAL | 漲跌價差 | 0.30 |
| odd_lot_filled | INTEGER | 零股填補標記（0=正常，1=零股成交但無整股價） | 0 |
| created_at | TIMESTAMP | 資料建立時間 | 2025-01-01 10:00:00 |

### 主鍵

- `(date, ticker)` - 日期和股票代號組合

### 注意事項

- 日期格式為 8 位數字字串（YYYYMMDD）
- 價格為台幣
- `odd_lot_filled = 1` 表示該筆資料是零股交易，價格欄位已用前一日收盤價填補
- 如果某天沒有交易，價格欄位可能為 NULL

---

## 2. tw_otc_stock_price_data

**說明**：儲存上櫃股票的每日股價資料，資料來源為櫃買中心 API。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式） | 20250101 |
| stock_name | TEXT | 股票名稱 | 某上櫃公司 |
| ticker | TEXT | 股票代號（主鍵） | 1234 |
| open | REAL | 開盤價 | 50.00 |
| high | REAL | 最高價 | 51.00 |
| low | REAL | 最低價 | 49.50 |
| close | REAL | 收盤價 | 50.50 |
| volume | INTEGER | 成交量（股數） | 500000 |
| turnover | REAL | 成交金額（元） | 25250000 |
| change | REAL | 漲跌價差 | 0.50 |
| odd_lot_filled | INTEGER | 零股填補標記（0=正常，1=零股成交但無整股價） | 0 |
| created_at | TIMESTAMP | 資料建立時間 | 2025-01-01 10:00:00 |

### 主鍵

- `(date, ticker)` - 日期和股票代號組合

### 注意事項

- 結構與 `tw_stock_price_data` 相同
- 上櫃股票不包含 ETF
- 權證（7開頭六位數）已被過濾，不包含在此表中

---

## 3. tw_price_indices_data

**說明**：儲存價格指數資料，資料來源為證交所 API。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式） | 20250101 |
| ticker | TEXT | 指數代號（主鍵） | TAWI |
| close_index | REAL | 收盤指數 | 18000.50 |
| change_sign | TEXT | 漲跌符號 | + |
| change_points | REAL | 漲跌點數 | 50.00 |
| change_pct | REAL | 漲跌百分比 | 0.28 |
| special_note | TEXT | 特殊註記 | NULL |
| created_at | TIMESTAMP | 資料建立時間 | 2025-01-01 10:00:00 |

### 主鍵

- `(date, ticker)` - 日期和指數代號組合

### 常見指數代號

- `TAWI` - 加權股價指數（台灣50）
- 其他指數代號請參考證交所資料

---

## 4. tw_return_indices_data

**說明**：儲存報酬指數資料，資料來源為證交所 API。

### 欄位說明

與 `tw_price_indices_data` 相同，但記錄的是報酬指數而非價格指數。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式） | 20250101 |
| ticker | TEXT | 指數代號（主鍵） | TAWI |
| close_index | REAL | 收盤指數 | 18000.50 |
| change_sign | TEXT | 漲跌符號 | + |
| change_points | REAL | 漲跌點數 | 50.00 |
| change_pct | REAL | 漲跌百分比 | 0.28 |
| special_note | TEXT | 特殊註記 | NULL |
| created_at | TIMESTAMP | 資料建立時間 | 2025-01-01 10:00:00 |

### 主鍵

- `(date, ticker)` - 日期和指數代號組合

---

## 5. business_cycle_data

**說明**：儲存景氣燈號資料，從月資料轉換為交易日資料。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式） | 20250101 |
| score | REAL | 景氣對策信號綜合分數 | 28.0 |
| val_shifted | REAL | 前一日數值（用於策略判斷） | 27.0 |
| signal | TEXT | 景氣對策信號（燈號顏色） | 綠燈 |

### 主鍵

- `date` - 日期（每天一筆資料）

### 燈號說明

- **藍燈**：SCORE ≤ 16（景氣低迷）
- **黃藍燈**：16 < SCORE ≤ 22
- **綠燈**：22 < SCORE ≤ 31（景氣穩定）
- **黃紅燈**：31 < SCORE < 38
- **紅燈**：SCORE ≥ 38（景氣過熱）

### 注意事項

- 原始資料為月資料（YYYYMM），已轉換為交易日資料
- `val_shifted` 是前一天的 `score` 值，用於避免使用未來資訊進行交易決策
- 每個月的所有交易日都使用該月的景氣燈號分數

---

## 資料關聯建議

### 在 Power BI 或其他 BI 工具中

1. **股價資料與景氣燈號關聯**：
   - `tw_stock_price_data.date` ←→ `business_cycle_data.date`
   - `tw_otc_stock_price_data.date` ←→ `business_cycle_data.date`

2. **查詢範例（SQL）**：
   ```sql
   SELECT 
       s.date,
       s.ticker,
       s.close,
       c.score,
       c.signal
   FROM tw_stock_price_data s
   LEFT JOIN business_cycle_data c ON s.date = c.date
   WHERE s.ticker = '006208'
   ORDER BY s.date DESC
   LIMIT 10;
   ```

### 常用查詢

#### 查詢特定股票的股價資料

```sql
SELECT * 
FROM tw_stock_price_data 
WHERE ticker = '006208' 
  AND date >= '20250101'
ORDER BY date DESC;
```

#### 查詢景氣燈號變化

```sql
SELECT date, score, signal, val_shifted
FROM business_cycle_data
WHERE date >= '20250101'
ORDER BY date DESC;
```

#### 合併股價與景氣燈號

```sql
SELECT 
    s.date,
    s.ticker,
    s.close,
    c.score,
    c.signal
FROM tw_stock_price_data s
LEFT JOIN business_cycle_data c ON s.date = c.date
WHERE s.ticker = '006208'
ORDER BY s.date DESC;
```

---

## 資料維護

### 資料更新

資料透過以下方式更新：

1. **景氣燈號**：使用 `main.py` 選項 1 從 CSV 讀取
2. **上市股票**：使用 `main.py` 選項 2 從證交所 API 收集
3. **上櫃股票**：使用 `main.py` 選項 2 從櫃買中心 API 收集

### 資料驗證

系統提供多種資料驗證功能：

- 選項 6：驗證股價資料（檢查異常）
- 選項 7：檢查資料完整性
- 選項 8：填補零值價格資料

### 資料清理

- 選項 9：刪除上櫃資料表中的權證資料

---

## 技術細節

### 日期格式

所有日期欄位使用 `YYYYMMDD` 格式（8位數字字串），例如：`20250101`

### NULL 值處理

- 價格欄位可能為 NULL（無交易或資料缺失）
- 成交量為 0 或 NULL 表示當日無交易
- 使用 `val_shifted` 欄位避免使用未來資訊

### 索引建議

為提高查詢效能，建議在以下欄位建立索引：

```sql
CREATE INDEX idx_stock_date ON tw_stock_price_data(date);
CREATE INDEX idx_stock_ticker ON tw_stock_price_data(ticker);
CREATE INDEX idx_otc_date ON tw_otc_stock_price_data(date);
CREATE INDEX idx_otc_ticker ON tw_otc_stock_price_data(ticker);
CREATE INDEX idx_cycle_date ON business_cycle_data(date);
```

---

## 資料統計

### 資料時間範圍

- **股票資料**：從 2015-01-01 至今（或收集開始日期）
- **景氣燈號**：從 CSV 檔案提供的日期範圍（通常為 1982 年至今）

### 資料量估算

假設從 2015 年開始收集：
- 交易日約 250 天/年
- 上市股票約 1000+ 檔
- 每年約 250,000+ 筆上市股票資料
- 上櫃股票約 700+ 檔
- 每年約 175,000+ 筆上櫃股票資料

總資料量約為數百 MB 到 1-2 GB（視收集時間範圍而定）。

---

## 參考資料

- 證交所公開資料 API 文件
- 櫃買中心公開資料 API 文件
- 景氣對策信號說明：政府開放資料平台

