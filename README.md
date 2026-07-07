# 🔋 Tesla Charging Health Monitor / Tesla 充電健康監測

A mobile-first **Streamlit** app for tracking Tesla charging behavior, analyzing battery-health proxy indicators, and generating reports.

This version includes built-in multilingual UI support:

- 繁體中文
- 简体中文
- English

Users can switch language from the floating language bubble at the top-right corner of every screen. Browser auto-translation is not required and is only a fallback.

> ⚠️ This app does **not** perform official Tesla battery diagnostics. Without kWh charged, real battery capacity, or BMS data, the app provides proxy analysis only.

---

## Features

- Built-in language switcher: Traditional Chinese, Simplified Chinese, English
- Photo upload / camera capture for Tesla dashboard images
- Gemini Vision OCR extraction for odometer and battery percentage
- Manual correction before saving
- Overview dashboard with KPIs and trend charts
- Period comparisons by year, quarter, month, week, day, and season
- Controlled comparisons for same-season / same-month / same-quarter analysis
- Battery-health proxy indicators and anomaly detection
- Markdown report generation and download
- CSV local storage for local development
- Optional Google Sheets storage for Streamlit Cloud persistence
- Mobile-first iPhone-friendly layout

---

## Project Structure

```text
tesla_charging_monitor/
├── app.py
├── translations.py
├── requirements.txt
├── README.md
├── GITHUB_DEPLOY.md
├── QUICKSTART_WINDOWS.txt
├── SETUP_GOOGLE_SHEETS.md
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── data/
│   └── charging_records.csv
├── temp/
│   └── .gitkeep
├── modules/
│   ├── analytics.py
│   ├── anomaly_detection.py
│   ├── data_store.py
│   ├── feature_engineering.py
│   ├── gsheets_store.py
│   ├── ocr_extractor.py
│   ├── report_generator.py
│   └── ui_components.py
├── assets/
└── static/
```

---

## Run Locally

```bash
cd C:\Users\Desktop\Git_Angela\Tesla\tesla_charging_monitor

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

---

## Deploy to GitHub

Your target repo:

```text
https://github.com/bhuang135/tesla-charging-monitor.git
```

Use these commands from your local project folder:

```bash
cd C:\Users\Desktop\Git_Angela\Tesla\tesla_charging_monitor

git init -b main
git remote set-url origin https://github.com/bhuang135/tesla-charging-monitor.git 2>NUL || git remote add origin https://github.com/bhuang135/tesla-charging-monitor.git

git add .
git commit -m "Upload multilingual Tesla charging monitor"
git push --force origin main
```

The final command intentionally overwrites the remote repository with your local version.

---

## Streamlit Cloud Settings

```text
Repository: bhuang135/tesla-charging-monitor
Branch: main
Main file path: app.py
```

After deployment, open:

```text
Manage app → Reboot app
```

---

## Secrets

For Gemini OCR, add this in Streamlit Cloud secrets or `.streamlit/secrets.toml` locally:

```toml
GEMINI_API_KEY = "your-gemini-api-key"
```

For persistent storage on Streamlit Cloud, use Google Sheets setup in `SETUP_GOOGLE_SHEETS.md`.

---

## Notes on Translation

This app uses a local deterministic translation layer in `translations.py`.

It translates:

- Streamlit labels
- Buttons
- Tabs
- Captions
- Markdown sections
- Plotly chart titles and axis labels
- Displayed dataframe column headers
- Downloaded Markdown reports

Browser translation can still be used as a fallback, but it is not recommended as the main product design because financial, battery, and Tesla-specific terms can be translated inconsistently.
