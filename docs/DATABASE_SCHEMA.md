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
6. [leading_indicators_data](#6-leading_indicators_data) - 領先指標構成項目
7. [coincident_indicators_data](#7-coincident_indicators_data) - 同時指標構成項目
8. [lagging_indicators_data](#8-lagging_indicators_data) - 落後指標構成項目
9. [composite_indicators_data](#9-composite_indicators_data) - 景氣指標與燈號（綜合指標）
10. [business_cycle_signal_components_data](#10-business_cycle_signal_components_data) - 景氣對策信號構成項目
11. [market_margin_data](#11-market_margin_data) - 大盤融資維持率資料

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

## 6. leading_indicators_data

**說明**：儲存領先指標構成項目資料，從月資料轉換為交易日資料。領先指標用於預測未來景氣變化。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式） | 20250101 |
| export_order_index | REAL | 外銷訂單動向指數(以家數計) | 50.5 |
| m1b_money_supply | REAL | 貨幣總計數M1B(百萬元) | 2500000 |
| m1b_yoy_month | REAL | M1B 月對月年增率(%) | 4.17 |
| m1b_yoy_momentum | REAL | M1B 年增率動能(%) | 0.5 |
| m1b_mom | REAL | M1B 月對月變化率(%) | 0.8 |
| m1b_vs_3m_avg | REAL | M1B 當月 vs 前三個月平均變化率(%) | 0.5 |
| stock_price_index | REAL | 股價指數(Index1966=100) | 18000.5 |
| employment_net_entry_rate | REAL | 工業及服務業受僱員工淨進入率(%) | 0.5 |
| building_floor_area | REAL | 建築物開工樓地板面積(千平方公尺) | 2000.5 |
| semiconductor_import | REAL | 名目半導體設備進口(新臺幣百萬元) | 50000 |
| created_at | TIMESTAMP | 資料建立時間 | 2025-01-01 10:00:00 |

### 主鍵

- `date` - 日期（每天一筆資料）

### 注意事項

- 原始資料為月資料（YYYYMM），已轉換為交易日資料
- 每個月的所有交易日都使用該月的指標數值
- 部分欄位可能為 NULL（歷史資料缺失）

### M1B 年增率欄位說明

- **m1b_yoy_month**：月對月年增率（%）
  - 計算方式：`(當前月份 M1B - 去年同月份 M1B) / 去年同月份 M1B * 100`
  - 例如：2025年1月 vs 2024年1月
  - 同一月的所有交易日使用相同的年增率值
  - 如果資料不足12個月，可能為 NULL

- **m1b_yoy_momentum**：年增率動能（%）
  - 計算方式：`當前年增率 - 上月年增率`
  - 例如：2025年1月的年增率 - 2024年12月的年增率
  - 用於判斷資金動能轉折點
  - 正值表示年增率上升（資金動能增強），負值表示年增率下降（資金動能減弱）
  - 如果資料不足或沒有上一個月的年增率，可能為 NULL

- **m1b_mom**：月對月變化率（%）
  - 計算方式：`(當月 M1B - 上月 M1B) / 上月 M1B * 100`
  - 例如：2025年1月 vs 2024年12月
  - 用於反映短期資金面變化，捕捉資金流動的短期趨勢
  - 正值表示 M1B 增加，負值表示 M1B 減少
  - 同一月的所有交易日使用相同的變化率值
  - 如果資料不足或沒有上一個月的資料，可能為 NULL

- **m1b_vs_3m_avg**：當月 M1B vs 前三個月平均變化率（%）
  - 計算方式：`(當月 M1B - 前三個月平均 M1B) / 前三個月平均 M1B * 100`
  - 前三個月平均 = (前第1月 + 前第2月 + 前第3月) / 3
  - 例如：2025年1月 vs (2024年10月 + 2024年11月 + 2024年12月) / 3
  - 用於平滑化短期波動，減少噪音，捕捉更穩定的資金面趨勢
  - 正值表示當月 M1B 高於前三個月平均，負值表示低於平均
  - 同一月的所有交易日使用相同的變化率值
  - 如果資料不足三個月，可能為 NULL
  - **注意**：此指標需要至少前三個月的資料，因此從 2015 年 4 月開始才有數據（假設資料從 2015 年 1 月開始）

**自動計算**：使用 `main.py` 選項 1 匯入領先指標資料時，系統會自動計算並更新這些欄位。

---

## 7. coincident_indicators_data

**說明**：儲存同時指標構成項目資料，從月資料轉換為交易日資料。同時指標反映當前景氣狀況。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式） | 20250101 |
| industrial_production_index | REAL | 工業生產指數(Index2021=100) | 105.5 |
| electricity_consumption | REAL | 電力(企業)總用電量(十億度) | 15.5 |
| manufacturing_sales_index | REAL | 製造業銷售量指數(Index2021=100) | 110.2 |
| wholesale_retail_revenue | REAL | 批發、零售及餐飲業營業額(十億元) | 1200.5 |
| overtime_hours | REAL | 工業及服務業加班工時(小時) | 10.5 |
| export_value | REAL | 海關出口值(十億元) | 800.5 |
| machinery_import | REAL | 機械及電機設備進口值(十億元) | 300.5 |
| created_at | TIMESTAMP | 資料建立時間 | 2025-01-01 10:00:00 |

### 主鍵

- `date` - 日期（每天一筆資料）

### 注意事項

- 原始資料為月資料（YYYYMM），已轉換為交易日資料
- 每個月的所有交易日都使用該月的指標數值
- 部分欄位可能為 NULL（歷史資料缺失）

---

## 8. lagging_indicators_data

**說明**：儲存落後指標構成項目資料，從月資料轉換為交易日資料。落後指標用於確認景氣變化趨勢。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式） | 20250101 |
| unemployment_rate | REAL | 失業率(%) | 3.5 |
| labor_cost_index | REAL | 製造業單位產出勞動成本指數(2021=100) | 105.5 |
| loan_interest_rate | REAL | 五大銀行新承做放款平均利率(年息百分比) | 2.5 |
| financial_institution_loans | REAL | 全體金融機構放款與投資(10億元) | 25000 |
| manufacturing_inventory | REAL | 製造業存貨價值(千元) | 1000000000 |
| created_at | TIMESTAMP | 資料建立時間 | 2025-01-01 10:00:00 |

### 主鍵

- `date` - 日期（每天一筆資料）

### 注意事項

- 原始資料為月資料（YYYYMM），已轉換為交易日資料
- 每個月的所有交易日都使用該月的指標數值
- 部分欄位可能為 NULL（歷史資料缺失）

---

## 9. composite_indicators_data

**說明**：儲存景氣指標與燈號綜合資料，從月資料轉換為交易日資料。包含領先、同時、落後指標的綜合指數。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式） | 20250101 |
| leading_index | REAL | 領先指標綜合指數 | 105.5 |
| leading_index_no_trend | REAL | 領先指標不含趨勢指數 | 102.3 |
| coincident_index | REAL | 同時指標綜合指數 | 103.2 |
| coincident_index_no_trend | REAL | 同時指標不含趨勢指數 | 101.5 |
| lagging_index | REAL | 落後指標綜合指數 | 104.8 |
| lagging_index_no_trend | REAL | 落後指標不含趨勢指數 | 103.1 |
| business_cycle_score | REAL | 景氣對策信號綜合分數 | 28.0 |
| business_cycle_signal | TEXT | 景氣對策信號（燈號顏色） | 綠燈 |
| created_at | TIMESTAMP | 資料建立時間 | 2025-01-01 10:00:00 |

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
- 每個月的所有交易日都使用該月的指標數值
- `business_cycle_score` 和 `business_cycle_signal` 與 `business_cycle_data` 表中的資料相同
- 部分欄位可能為 NULL（歷史資料缺失）

---

## 10. business_cycle_signal_components_data

**說明**：儲存景氣對策信號構成項目資料，從月資料轉換為交易日資料。這些指標用於計算景氣對策信號綜合分數。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式） | 20250101 |
| m1b_money_supply | REAL | 貨幣總計數M1B(百萬元) | 2500000 |
| m1b_yoy_month | REAL | M1B 月對月年增率(%) | 4.17 |
| m1b_yoy_rolling_12m | REAL | M1B 滾動12個月年增率(%) | 8.70 |
| stock_price_index | REAL | 股價指數(Index1966=100) | 18000.5 |
| industrial_production_index | REAL | 工業生產指數(Index2021=100) | 105.5 |
| overtime_hours | REAL | 工業及服務業加班工時(小時) | 10.5 |
| export_value | REAL | 海關出口值(十億元) | 800.5 |
| machinery_import | REAL | 機械及電機設備進口值(十億元) | 300.5 |
| manufacturing_sales_index | REAL | 製造業銷售量指數(Index2021=100) | 110.2 |
| wholesale_retail_revenue | REAL | 批發、零售及餐飲業營業額(十億元) | 1200.5 |
| created_at | TIMESTAMP | 資料建立時間 | 2025-01-01 10:00:00 |

### 主鍵

- `date` - 日期（每天一筆資料）

### 注意事項

- 原始資料為月資料（YYYYMM），已轉換為交易日資料
- 每個月的所有交易日都使用該月的指標數值
- 這些指標是計算景氣對策信號綜合分數的構成項目
- 部分欄位可能為 NULL（歷史資料缺失）

---

## 資料關聯建議

### 在 Power BI 或其他 BI 工具中

1. **股價資料與景氣燈號關聯**：
   - `tw_stock_price_data.date` ←→ `business_cycle_data.date`
   - `tw_otc_stock_price_data.date` ←→ `business_cycle_data.date`

2. **股價資料與景氣指標關聯**：
   - `tw_stock_price_data.date` ←→ `leading_indicators_data.date`
   - `tw_stock_price_data.date` ←→ `coincident_indicators_data.date`
   - `tw_stock_price_data.date` ←→ `lagging_indicators_data.date`
   - `tw_stock_price_data.date` ←→ `composite_indicators_data.date`
   - `tw_stock_price_data.date` ←→ `business_cycle_signal_components_data.date`

3. **景氣指標之間的關聯**：
   - 所有景氣指標資料表都使用 `date` 作為主鍵，可以互相關聯
   - `composite_indicators_data` 包含綜合指標，可與其他構成項目資料表關聯

4. **查詢範例（SQL）**：
   ```sql
   -- 股價與景氣燈號
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
   
   -- 股價與領先指標
   SELECT 
       s.date,
       s.ticker,
       s.close,
       l.stock_price_index,
       l.m1b_money_supply,
       l.export_order_index
   FROM tw_stock_price_data s
   LEFT JOIN leading_indicators_data l ON s.date = l.date
   WHERE s.ticker = '006208'
   ORDER BY s.date DESC
   LIMIT 10;
   
   -- 綜合查詢：股價、景氣燈號、領先指標
   SELECT 
       s.date,
       s.ticker,
       s.close,
       c.score,
       c.signal,
       l.stock_price_index,
       l.m1b_money_supply,
       co.coincident_index,
       la.unemployment_rate
   FROM tw_stock_price_data s
   LEFT JOIN business_cycle_data c ON s.date = c.date
   LEFT JOIN leading_indicators_data l ON s.date = l.date
   LEFT JOIN coincident_indicators_data co ON s.date = co.date
   LEFT JOIN lagging_indicators_data la ON s.date = la.date
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

## 11. market_margin_data

**說明**：儲存大盤融資維持率資料，資料來源為證交所 MI_MARGN API。

### 欄位說明

| 欄位名稱 | 資料型別 | 說明 | 範例 |
|---------|---------|------|------|
| date | TEXT | 日期（YYYYMMDD 格式，主鍵） | 20260123 |
| margin_buy_units | TEXT | 融資買進（交易單位） | 523,402 |
| margin_sell_units | TEXT | 融資賣出（交易單位） | 498,874 |
| margin_cash_repay_units | TEXT | 融資現金(券)償還（交易單位） | 12,625 |
| margin_prev_balance_units | TEXT | 融資前日餘額（交易單位） | 8,193,989 |
| margin_today_balance_units | TEXT | 融資今日餘額（交易單位） | 8,205,892 |
| short_buy_units | TEXT | 融券買進（交易單位） | 29,235 |
| short_sell_units | TEXT | 融券賣出（交易單位） | 20,451 |
| short_cash_repay_units | TEXT | 融券現金(券)償還（交易單位） | 4,958 |
| short_prev_balance_units | TEXT | 融券前日餘額（交易單位） | 311,678 |
| short_today_balance_units | TEXT | 融券今日餘額（交易單位） | 297,936 |
| margin_buy_amount | TEXT | 融資買進（仟元） | 32,913,296 |
| margin_sell_amount | TEXT | 融資賣出（仟元） | 27,977,075 |
| margin_cash_repay_amount | TEXT | 融資現金(券)償還（仟元） | 593,667 |
| margin_prev_balance_amount | TEXT | 融資前日餘額（仟元） | 371,734,424 |
| margin_today_balance_amount | TEXT | 融資今日餘額（仟元） | 376,076,978 |
| margin_shares_total | REAL | 所有融資股數總和（數值化，計算欄位） | 8193989.0 |
| margin_balance | REAL | 大盤融資餘額（元，數值化，計算欄位） | 371734424000.0 |
| margin_market_value | REAL | 所有融資股票市值（元，計算欄位） | 371734424000.0 |
| margin_maintenance_ratio | REAL | 大盤融資維持率（計算欄位） | 1.0 |
| created_at | TIMESTAMP | 資料建立時間 | 2026-01-23 10:00:00 |

### 主鍵

- `date` - 日期（YYYYMMDD 格式）

### 計算欄位說明

- **margin_maintenance_ratio（大盤融資維持率）**：
  - 計算公式：`(所有融資股數 × 股票收盤價) / 大盤融資餘額`
  - 由於 API 只提供市場整體數據，使用近似方法計算
  - 近似方法：`融資維持率 ≈ 融資股票市值 / 融資餘額`

### 注意事項

- 日期格式為 8 位數字字串（YYYYMMDD）
- 原始數據欄位（units, amount）以字串格式儲存（包含逗號）
- 計算欄位（margin_shares_total, margin_balance, margin_market_value, margin_maintenance_ratio）為數值型
- 融資金額單位為「仟元」，計算時需轉換為「元」（乘以 1000）
- 建議使用「前日餘額」欄位作為準確數據（根據證交所說明）

### 查詢範例

```sql
-- 查詢最近 10 天的融資維持率
SELECT 
    date,
    margin_prev_balance_amount,
    margin_shares_total,
    margin_maintenance_ratio
FROM market_margin_data
WHERE margin_maintenance_ratio IS NOT NULL
ORDER BY date DESC
LIMIT 10;

-- 查詢股價與融資維持率
SELECT 
    s.date,
    s.ticker,
    s.close,
    m.margin_maintenance_ratio,
    m.margin_prev_balance_amount
FROM tw_stock_price_data s
LEFT JOIN market_margin_data m ON s.date = m.date
WHERE s.ticker = '006208'
ORDER BY s.date DESC
LIMIT 10;
```

---

## 資料維護

### 資料更新

資料透過以下方式更新：

1. **景氣燈號與指標**：使用 `main.py` 選項 1 從 CSV 讀取
   - `business_cycle_data` - 景氣燈號資料
   - `leading_indicators_data` - 領先指標構成項目
   - `coincident_indicators_data` - 同時指標構成項目
   - `lagging_indicators_data` - 落後指標構成項目
   - `composite_indicators_data` - 景氣指標與燈號（綜合指標）
   - `business_cycle_signal_components_data` - 景氣對策信號構成項目
   - 支援一鍵更新所有景氣指標資料
2. **上市股票**：使用 `main.py` 選項 2 從證交所 API 收集
3. **上櫃股票**：使用 `main.py` 選項 2 從櫃買中心 API 收集
4. **融資維持率**：使用 `main.py` 選項 13 從證交所 MI_MARGN API 收集
   - `market_margin_data` - 大盤融資維持率資料

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
CREATE INDEX idx_margin_date ON market_margin_data(date);
```

---

## 資料統計

### 資料時間範圍

- **股票資料**：從 2015-01-01 至今（或收集開始日期）
- **景氣燈號**：從 CSV 檔案提供的日期範圍（通常為 1982 年至今）
- **融資維持率**：從 2015-01-01 至今（或收集開始日期）

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

