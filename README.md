# Business Cycle Investment Strategy System

**[Chinese Introduction (繁體中文)](README_zh-TW.md)**

---

## Overview

This project is a **quantitative backtesting and data pipeline platform** based on Taiwan's business cycle indicator (景氣燈號) and macroeconomic indicators. It helps you:

- Import and process **business cycle and macroeconomic data** (NSC indicators, M1B, merged indicators).
- Collect **stock prices** (listed/OTC), **margin trading data**, and **VIX** (intraday → monthly K-line → derivatives).
- Compute **technical indicators** (daily/monthly) and **VIX derivatives**, and maintain a **Chinese-alias VIEW** for all tables.
- Run **multi-strategy backtests** (TEJ-style rules and Orange ML) with validation and reports.
- Use a **one-click Orange pipeline** (collect → derive → export) for prediction workflows.

**Database scale** (as of [results/資料庫筆數統計.txt](results/資料庫筆數統計.txt)): about **11.16 million rows** across all tables. Listed/ETF: 1,516 tickers (2010–2026); OTC: 5,304 tickers (2010–2026); business cycle and composite indicators: ~10.9k rows (1982–2026); VIX raw (TFE): ~94.8k; VIX monthly/derivatives: 163; margin data: ~3.9k (aggregated) and ~1.72M (exchange raw); backtest results: ~1.62M rows.

**Who is this for:** Quant and business-cycle strategy developers, researchers who need Taiwan market data and reproducible backtests.

---

## Performance Snapshot

<img src="photo/TEJ成果還原_page-0001.jpg" alt="TEJ Strategy Backtest Report - Page 1" width="800">

<img src="photo/TEJ成果還原_page-0002.jpg" alt="TEJ Strategy Backtest Report - Page 2" width="800">

---

## Quick Start

### Want to understand the system first?

See [Project context document](docs/PROJECT_CONTEXT.md).

### First time setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set database path** (if needed)
   
   Default path: `D:\all_data\taiwan_stock_all_data.db`
   
   To use a different path, edit the default in `data_collection/database_manager.py`.

3. **Run the main program**
   ```bash
   python main.py
   ```

4. **Follow the menu** (options 0–18)
   - Option 1: Load business cycle / indicator data
   - Option 2: Collect stock data
   - Option 12: Run backtest
   - Other options: see "Feature overview" below.

### Troubleshooting

- **Database not found?** Check the database path.
- **Package install failed?** Ensure Python 3.8+ is installed.
- **Runtime error?** Ensure all dependencies are installed (see "Dependencies" below).

---

## Feature Overview

### Option 1: Load business cycle and indicator data

**When to use:** First-time setup or when you need the latest business cycle data.

**How:** Run `python main.py` → choose option 1 → wait for completion.

**What happens:** System loads business cycle data from CSV and converts it to daily series for strategies.

**Data source:** `business_cycle/景氣指標與燈號.csv`

---

### Option 2: Collect stock and ETF data

**When to use:** First-time setup or when you need the latest price data.

**How:** Run `python main.py` → choose option 2 → wait for download (may take a while).

**What happens:** System downloads listed stock and ETF prices from the exchange API and stores them in the database.

**Notes:** 3–5 second delay between requests to avoid rate limits; automatic retry up to 3 times on failure.

---

### Option 12: Run backtest

**When to use:** To test strategy performance or compare strategies.

**How:** Ensure options 1 and 2 are done → run `python main.py` → option 12 → choose strategy(ies) → enter date range (or default) → wait for completion.

**Strategies:**

| Strategy | Description | Use case |
|----------|-------------|----------|
| **Business cycle (TEJ)** | Buy/sell by cycle lights | Follow the business cycle |
| **Orange ML** | AI-based price prediction | Use ML signals |
| **Buy & hold** | Hold equity | Benchmark |

**Backtest defaults:** Start 2020-01-01, end 2025-11-30, initial capital 1,000,000 TWD.

**Output:** Excel with daily portfolio value, trades, and metrics (return, Sharpe, max drawdown, etc.).

---

### Option 14: Download and recalculate VIX monthly K-line

**When to use:** When you need up-to-date VIX data or to fill missing trading days for the current month.

**How:** Run `python main.py` → option 14. The system detects missing trading days, downloads raw VIX data, parses it, inserts into `TFE_VIX_data`, recalculates monthly K-lines, and updates `VIX_data`.

**Data source:** TAIFEX public API (`https://www.taifex.com.tw/cht/7/getVixData`).

**Notes:** Retries up to 3 times; raw files under `VIX_dictionary_put_in_database/TFE_rawdata/raw_data/`.

---

### Option 13: Collect margin (financing) data

**When to use:** When you need market-wide margin data and derived metrics (e.g. margin balance change rate, buy/sell ratio).

**How:** Run `python main.py` → option 13 → enter date range (default 2015–2025).

**What happens:** Downloads margin data from the exchange MI_MARGN API, writes to `market_margin_data`, and computes derived indicators.

---

### Option 15: Compute VIX derivatives

**When to use:** After option 14 has produced VIX monthly K-lines and you need derivative fields (change, range, momentum, lags, moving averages).

**How:** Run `python main.py` → option 15.

**What happens:** Computes fields such as vix_change, vix_change_pct, vix_range, vix_mom, vix_ma3 and writes them to `VIX_data`.

---

### Option 16: Create Chinese-alias VIEWs

**When to use:** When you want to query tables using Chinese column names (e.g. for reports or BI).

**How:** Run `python main.py` → option 16.

**What happens:** Creates VIEWs for main tables with Chinese column aliases.

---

### Option 17: Compute technical indicators (daily / monthly)

**When to use:** When you need daily or monthly technical indicators (e.g. moving averages, volatility) for strategies or Orange export.

**How:** Run `python main.py` → option 17 → choose daily or monthly as prompted.

**What happens:** Computes the selected indicators and writes them to the corresponding tables.

---

### Option 18: Orange one-click pipeline

**When to use:** To run the full flow: collect → derive → export Orange CSV (daily/monthly) in one go.

**How:** Run `python main.py` → option 18 → follow the script menu.

**What happens:** Calls `scripts/run_orange_pipeline.py` to chain data collection, derivation, and Orange export.

---

## Orange ML strategy

### What it is

A strategy that uses a trained ML model to predict prices and trade when actual price deviates from prediction (e.g. buy when undervalued, sell when overvalued).

### How it works

1. **Model prediction:** Trained model predicts price.
2. **Compare:** Actual vs predicted price.
3. **Trade:** e.g. buy if actual < 95% of predicted; sell if actual > 105% of predicted.

### Requirements

- Orange model file (.pkcls) — train in Orange first.
- Business cycle data (option 1) and stock price data (option 2).

### Usage

1. Install Orange3 and PyQt5: `pip install orange3 PyQt5`
2. Prepare the Orange model file.
3. In backtest (option 12), select the Orange prediction strategy.

**Details:** [Orange integration report](docs/ORANGE_INTEGRATION_REPORT.md)

---

## Strategy performance

### Backtest results (2020–2025, illustrative)

| Strategy | Ann. return | Risk-adjusted | Max drawdown | Note |
|----------|-------------|---------------|--------------|------|
| **Orange** | 23.5% | ⭐⭐⭐⭐ | -34% | Highest return |
| **Short-term bond** | 21.7% | ⭐⭐⭐⭐⭐ | -26% | Lower risk |
| **Buy & hold** | 18.2% | ⭐⭐⭐ | -34% | Benchmark |
| **Cash hedge** | 17.3% | ⭐⭐⭐⭐ | -27% | Conservative |

**Metrics:** Ann. return = average yearly return; risk-adjusted = Sharpe-style; max drawdown = worst peak-to-trough loss.

### Choosing a strategy

- **Highest return?** → Orange ML.
- **Stable return?** → Short-term bond.
- **Conservative?** → Cash hedge.

---

## System layout

```
Business_Cycle_stratgy/
├── data_collection/          # Data collection
│   ├── cycle_data_collector.py       # Business cycle (CSV)
│   ├── stock_data_collector.py      # Listed stocks/ETFs
│   ├── otc_data_collector.py        # OTC stocks
│   ├── indicator_data_collector.py   # Indicators & merged macro
│   ├── m1b_calculator.py             # M1B yoy & momentum
│   ├── margin_data_collector.py     # Margin (exchange API)
│   ├── vix_derivatives.py           # VIX derivatives
│   ├── technical_indicator_calculator.py  # Tech indicators
│   └── database_manager.py           # DB access
├── backtesting/              # Backtest
│   ├── backtest_engine_new.py     # Engine
│   ├── strategy_tej.py            # TEJ cycle strategy
│   ├── strategy_orange.py         # Orange ML strategy
│   ├── orange_model_loader.py     # Orange model loader
│   └── chart_generator.py         # Charts
├── orange_data_export/       # Orange export
│   ├── export_for_prediction.py   # Export for prediction
│   └── inspect_model.py           # Model inspection
├── utils/                    # Utilities
│   └── timestamp_converter.py   # Timestamp conversion
├── VIX_dictionary_put_in_database/  # VIX download, parse, monthly K
├── scripts/
│   ├── export_orange_data.py     # Orange data export
│   └── run_orange_pipeline.py   # One-click Orange pipeline
├── docs/
├── main.py                   # Entry point
├── requirements.txt
└── README.md
```

---

## Strategy logic (summary)

### Business cycle (TEJ)

- **Blue (score ≤ 16):** Buy equity (e.g. 006208), sell hedge.
- **Red (score ≥ 38):** Sell equity, buy hedge (bonds/cash).
- **Green/Yellow:** Buy on first entry into range.

### Orange ML

- **Buy:** Actual price < 95% of predicted.
- **Sell:** Actual price > 105% of predicted.
- **Risk:** Position size 20%–100% by prediction stability.

---

## Data sources

### Business cycle

- **Source:** Government open data.
- **File:** `business_cycle/景氣指標與燈號.csv`
- **Update:** Monthly.

### Stock prices

- **Source:** TWSE / TPEx APIs.
- **Storage:** SQLite.
- **Update:** Option 2 or 5.

---

## Dependencies

### Required

| Package | Purpose |
|---------|---------|
| `pandas` | Data handling |
| `numpy` | Numerics |
| `requests` | API calls |
| `matplotlib` | Plots |
| `plotly` | Interactive charts |
| `openpyxl` | Excel I/O |

### Optional

| Package | When needed |
|---------|-------------|
| `orange3` | Orange strategy |
| `PyQt5` | Orange strategy |
| `pandas_market_calendars` | Trading calendar |

### Install

```bash
pip install -r requirements.txt
```

For Orange strategy also:

```bash
pip install orange3 PyQt5
```

---

## FAQ

### Install

**Q: Package install fails?**  
A: Use Python 3.8+, run `python -m pip install --upgrade pip`, then install packages one by one if needed.

**Q: What do I need for Orange strategy?**  
A: `orange3` and `PyQt5`: `pip install orange3 PyQt5`

### Usage

**Q: Which strategy to choose?**  
A: Orange for highest return; short-term bond for stability; cash hedge for conservative.

**Q: Why does backtest differ from live trading?**  
A: Backtest uses historical data and closing prices; live trading has slippage, liquidity, and execution delays.

**Q: Where are strategy parameters?**  
A: TEJ in `backtesting/strategy_tej.py`; Orange in `backtesting/strategy_orange.py` (see comments around lines 89–125).

**Q: General errors?**  
A: Check dependencies, database path, and that options 1 and 2 have been run; read the error message.

### Data

**Q: Where is the database?**  
A: Default `D:\all_data\taiwan_stock_all_data.db`; override in `data_collection/database_manager.py`.

**Q: Is the DB uploaded to GitHub?**  
A: No; it is in `.gitignore`. Keep your copy locally.

**Q: How to update data?**  
A: Option 2 for stocks; option 5 for batch update.

---

## Database schema

SQLite stores all data.

**Main tables:**

- `tw_stock_price_data` — Listed stocks/ETFs daily prices
- `tw_otc_stock_price_data` — OTC daily prices
- `business_cycle_data` — Business cycle daily
- `market_margin_data` — Margin and derivatives (option 13)
- `TFE_VIX_data` — VIX intraday raw (option 14)
- `VIX_data` — VIX monthly K-line and derivatives (options 14 / 15)

Row counts and date ranges: [results/資料庫筆數統計.txt](results/資料庫筆數統計.txt) or the database scale table in [README_zh-TW.md](README_zh-TW.md).

**Full schema:** [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)

---

## Other features

### Data validation and fixes (options 6–9)

- **6:** Validate prices (outliers)
- **7:** Check data integrity
- **8:** Fill zero/missing prices
- **9:** Remove warrant records from OTC table

### Other menu options (13–18)

- **13:** Collect margin data (2015–2025, with derivatives)
- **14:** Download and recalculate VIX monthly K-line
- **15:** Compute VIX derivatives
- **16:** Create Chinese-alias VIEWs
- **17:** Compute technical indicators (daily/monthly)
- **18:** Orange one-click pipeline

### Analysis tools

- [Power BI setup](docs/POWER_BI_SETUP.md)
- [Orange integration report](docs/ORANGE_INTEGRATION_REPORT.md)

---

## License

For **learning and research** only.

**Disclaimer:** Strategies and content here are not investment advice. Investing involves risk. Past performance does not guarantee future results.

---

## References

- TEJ: From business cycle lights to asset rotation (quant strategy)
- TWSE / TPEx public APIs
- National Development Council — business cycle indicator

---

## More

- **Technical docs:** `docs/` and [PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md)
- **Database:** [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)
- **Orange:** [ORANGE_INTEGRATION_REPORT.md](docs/ORANGE_INTEGRATION_REPORT.md)
- **GitHub:** [GITHUB_SETUP.md](docs/GITHUB_SETUP.md)
