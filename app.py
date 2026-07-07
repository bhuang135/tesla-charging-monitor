"""
Tesla 充電健康監測 App
======================
追蹤並分析 Tesla 充電行為，跨多個時間區間（年、季、月、週、日、季節）。
提供基於里程、電量百分比、充電頻率與行為模式的**電池健康代理（proxy）分析**。

注意：本工具不執行正式的 Tesla 電池診斷。沒有 kWh 充電量、實際電池容量或 BMS
資料的情況下，只能做代理分析。

啟動方式：streamlit run app.py
"""

from __future__ import annotations

# --- 確保 modules 資料夾在 sys.path 上，避免 Windows 工作目錄問題 ---
import os as _os
import sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)

# --- 診斷：若 modules 缺失，給出清楚的錯誤訊息 ---
_MODULES_DIR = _os.path.join(_HERE, "modules")
if not _os.path.isdir(_MODULES_DIR):
    import streamlit as _st
    _st.error(
        f"❌ 缺少 `modules/` 資料夾。\n\n"
        f"此程式位於：\n`{_HERE}`\n\n"
        f"預期找到資料夾：\n`{_MODULES_DIR}`\n\n"
        f"目前 `{_HERE}` 內含：\n```\n"
        + "\n".join(sorted(_os.listdir(_HERE)))
        + "\n```\n\n"
        "請確認專案結構為：\n"
        "```\n"
        "Tesla/\n"
        "├── app.py\n"
        "└── modules/\n"
        "    ├── __init__.py\n"
        "    ├── data_store.py\n"
        "    └── ... (其他模組)\n"
        "```"
    )
    _st.stop()

_INIT_FILE = _os.path.join(_MODULES_DIR, "__init__.py")
if not _os.path.isfile(_INIT_FILE):
    import streamlit as _st
    _st.error(
        f"❌ 缺少檔案：`modules/__init__.py`\n\n"
        f"請在 `{_MODULES_DIR}` 中新增一個空的 `__init__.py` 檔案。"
    )
    _st.stop()
# -----------------------------------------------------------------

import os
from datetime import date, datetime, timezone, timedelta

import pandas as pd
import streamlit as st

# 本地模組
from modules.data_store import DataStore
from modules.feature_engineering import recompute_features
from modules.ocr_extractor import extract_from_image
from modules.analytics import (
    overview_kpis,
    chart_count_by_year,
    chart_avg_miles_diff_by_year,
    chart_avg_start_battery_by_year,
    chart_avg_final_battery_by_year,
    chart_battery_added_over_time,
    chart_odometer_trend,
    chart_monthly_frequency,
    aggregate,
    chart_aggregate,
    same_period_across_years,
    chart_same_period_across_years,
)
from modules.anomaly_detection import (
    detect_anomalies,
    DEFAULT_THRESHOLDS,
    health_proxy_summary,
)
from modules.report_generator import build_report
from modules.ui_components import (
    plotly_static_config,
    inject_mobile_css,
    kpi_card,
    section_header,
    badge,
)

# ---------- 頁面設定 ----------
# 嘗試載入 app icon；失敗則 fallback 到 emoji
_ICON_PATH = _os.path.join(_HERE, "static", "app_icon.png")
try:
    from PIL import Image as _PILImage
    _page_icon = _PILImage.open(_ICON_PATH) if _os.path.exists(_ICON_PATH) else "🔋"
except Exception:
    _page_icon = "🔋"

st.set_page_config(
    page_title="Tesla Charging Health Monitor",
    page_icon=_page_icon,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------- Built-in multilingual UI ----------
from translations import init_language_selector, patch_streamlit, tr, translate_text
init_language_selector(st)
patch_streamlit(st)

# ============================================================
# iPhone「加入主畫面」icon 設定
# ============================================================
# ⚠️ Streamlit 限制：Safari 在「加入主畫面」時讀取的是**初始 HTML 載入時**
# 就存在於 <head> 中的 <link rel="apple-touch-icon">。但 Streamlit 是
# React SPA，所有 client-side 注入的 meta tag 都是在 React app 載入後才出現，
# 此時 Safari 早已快取了預設 icon。
#
# 我們能做的：
# 1. 用 components.html 在 parent document 注入所有必要的 meta tag
# 2. 用 cache-busting query param (?v=N) 強制 Safari 重新下載
# 3. 同時注入多個 sizes 的 icon，給 iOS 最大機會抓到
# 4. 即使重新「加入主畫面」也未必成功 — 詳見 README 中的「iPhone 測試步驟」
# ============================================================
import streamlit.components.v1 as _components

# Cache buster — 每次圖示更新時改這個版本號（強制 Safari/Browser 重新下載）
ICON_VERSION = "2"

_components.html(
    f"""
    <script>
    (function() {{
      try {{
        var head = window.parent.document.head;
        var v = '?v={ICON_VERSION}';

        // ===== 1. 清除既有的 icon link =====
        head.querySelectorAll(
          'link[rel="apple-touch-icon"], '
          + 'link[rel="apple-touch-icon-precomposed"], '
          + 'link[rel="shortcut icon"], '
          + 'link[rel="icon"]'
        ).forEach(el => el.remove());

        // ===== 2. apple-touch-icon — 標準 + 多個 sizes =====
        // 沒有 sizes 屬性的（iOS fallback）
        var t1 = window.parent.document.createElement('link');
        t1.rel = 'apple-touch-icon';
        t1.href = '/app/static/apple-touch-icon.png' + v;
        head.appendChild(t1);

        // 180x180 — iPhone Plus/Pro Max @3x（最常用）
        var t2 = window.parent.document.createElement('link');
        t2.rel = 'apple-touch-icon';
        t2.setAttribute('sizes', '180x180');
        t2.href = '/app/static/apple-touch-icon.png' + v;
        head.appendChild(t2);

        // 152x152 — iPad
        var t3 = window.parent.document.createElement('link');
        t3.rel = 'apple-touch-icon';
        t3.setAttribute('sizes', '152x152');
        t3.href = '/app/static/apple-touch-icon.png' + v;
        head.appendChild(t3);

        // 120x120 — iPhone @2x
        var t4 = window.parent.document.createElement('link');
        t4.rel = 'apple-touch-icon';
        t4.setAttribute('sizes', '120x120');
        t4.href = '/app/static/apple-touch-icon.png' + v;
        head.appendChild(t4);

        // precomposed (舊版 iOS 兼容)
        var t5 = window.parent.document.createElement('link');
        t5.rel = 'apple-touch-icon-precomposed';
        t5.href = '/app/static/apple-touch-icon.png' + v;
        head.appendChild(t5);

        // ===== 3. 一般 favicon + shortcut icon =====
        var fav = window.parent.document.createElement('link');
        fav.rel = 'icon';
        fav.type = 'image/png';
        fav.href = '/app/static/app_icon.png' + v;
        head.appendChild(fav);

        var shortcut = window.parent.document.createElement('link');
        shortcut.rel = 'shortcut icon';
        shortcut.href = '/app/static/app_icon.png' + v;
        head.appendChild(shortcut);

        // ===== 4. iPhone 主畫面 meta tags =====
        var titleMeta = window.parent.document.createElement('meta');
        titleMeta.name = 'apple-mobile-web-app-title';
        titleMeta.content = 'Tesla Monitor';
        head.appendChild(titleMeta);

        var capableMeta = window.parent.document.createElement('meta');
        capableMeta.name = 'apple-mobile-web-app-capable';
        capableMeta.content = 'yes';
        head.appendChild(capableMeta);

        var statusMeta = window.parent.document.createElement('meta');
        statusMeta.name = 'apple-mobile-web-app-status-bar-style';
        statusMeta.content = 'black-translucent';
        head.appendChild(statusMeta);

        // Android / Chrome
        var themeMeta = window.parent.document.createElement('meta');
        themeMeta.name = 'theme-color';
        themeMeta.content = '#0a0a0c';
        head.appendChild(themeMeta);

        // 也更新 document title (主畫面 fallback 名稱)
        if (window.parent.document.title.indexOf('Tesla') === -1) {{
          window.parent.document.title = 'Tesla Monitor';
        }}
      }} catch (e) {{ /* no-op */ }}
    }})();
    </script>
    """,
    height=0,
)

# inject_mobile_css 留到 main page 才呼叫（home/loading 有自己的 CSS）

# ---------- 常數 ----------
DATA_DIR = "data"
TEMP_DIR = "temp"
CSV_PATH = os.path.join(DATA_DIR, "charging_records.csv")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


# ---------- 儲存後端自動選擇 ----------
# Streamlit Cloud 的檔案系統是 ephemeral — 每次 reboot 都會清空。
# 所以如果偵測到 secrets.toml 中設有 Google Sheets 憑證，就改用 GSheetsStore；
# 否則仍用本地 CSV（適合 localhost 開發）。
def _make_store():
    try:
        has_gcp = bool(st.secrets.get("gcp_service_account"))
        has_url = bool(st.secrets.get("gsheets", {}).get("spreadsheet_url"))
        if has_gcp and has_url:
            from modules.gsheets_store import GSheetsStore
            return GSheetsStore(worksheet_name="charging_records"), "gsheets"
    except Exception:
        pass
    return DataStore(CSV_PATH), "csv"

store, _STORE_BACKEND = _make_store()


# ---------- 時區處理 ----------
# 🔒 時區固定為 America/Los_Angeles（不依使用者瀏覽器或 server 時區）
USER_TZ = "America/Los_Angeles"


def _detect_user_timezone() -> str:
    """傳回固定時區 — 為了與其他程式碼介面相容而保留此函式。"""
    return USER_TZ


def get_user_today() -> date:
    """
    回傳 Los Angeles 時區的今天日期。
    這是 deployment-safe 的：不論 Streamlit Cloud server 跑在哪個時區，
    使用者看到的都是 LA 當地的今日。
    自動處理 DST（夏令時）切換。
    """
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(USER_TZ)).date()
    except Exception:
        # Fallback：假設標準時間 UTC-8（不考慮 DST，僅在 zoneinfo 不可用時使用）
        return (datetime.now(timezone.utc) + timedelta(hours=-8)).date()


# ---------- Helpers ----------
def load_df() -> pd.DataFrame:
    df = store.load()
    if df.empty:
        return df
    return recompute_features(df)


def metric_options():
    return {
        "充電次數": "charging_count",
        "平均充電間隔里程": "avg_miles_diff",
        "平均起始電量 %": "avg_start_battery_pct",
        "平均結束電量 %": "avg_final_battery_pct",
        "平均增加電量 %": "avg_battery_pct_added",
        "低電量充電比例": "low_battery_rate",
    }


def cleanup_temp_files():
    if not os.path.isdir(TEMP_DIR):
        return
    for f in os.listdir(TEMP_DIR):
        try:
            os.remove(os.path.join(TEMP_DIR, f))
        except Exception:
            pass


# ====================================================================
# Tesla Welcome / Loading 畫面（取代原本的 CSS splash overlay）
# ====================================================================
import base64 as _b64
import time

def _img_to_data_uri(path: str, mime: str = "image/jpeg") -> str:
    """讀取圖片並轉成 data URI。"""
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as _f:
            return f"data:{mime};base64," + _b64.b64encode(_f.read()).decode("ascii")
    except Exception:
        return ""


def _render_home_page():
    """Tesla 風格 Welcome 首頁 — 強制一螢幕 fit，所有元素在 100dvh 內。"""
    car_uri = _img_to_data_uri(os.path.join(_HERE, "assets", "model3_real.jpg"))

    # 檢查使用者是否點了「進入」按鈕（用 query param）
    qp = st.query_params
    if qp.get("enter") == "1":
        st.query_params.clear()
        st.session_state.page = "loading"
        st.session_state.loading_started_at = time.time()
        st.rerun()

    css = """
<style>
[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
#MainMenu, footer { visibility: hidden; }
.block-container {
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
}
[data-testid="stAppViewContainer"] > .main { background: #000 !important; }
[data-testid="stAppViewContainer"] { background: #000 !important; }
html, body {
    background: #000 !important;
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes carFloat {
    0%, 100% { transform: translateX(-50%) translateY(0); }
    50%      { transform: translateX(-50%) translateY(-3px); }
}
@keyframes pulseRedDot {
    0%, 100% { opacity: 1; box-shadow: 0 0 4px rgba(204,43,50,0.8); }
    50%      { opacity: 0.4; box-shadow: 0 0 10px rgba(204,43,50,0.4); }
}

/* ====== 主容器 — 強制 100dvh，內容用 flex 自動分配 ====== */
.tesla-home {
    background: #000;
    color: #f3f5f7;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", system-ui, sans-serif;
    max-width: 430px;
    width: 100%;
    margin: 0 auto;
    height: 100vh;
    height: 100dvh;
    max-height: 100dvh;
    padding: clamp(0.4rem, 1.2vh, 0.8rem) clamp(0.8rem, 4vw, 1.25rem) clamp(0.4rem, 1vh, 0.6rem);
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
    gap: 0.4vh;
}

/* 頂部 */
.home-topbar {
    flex: 0 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    animation: fadeInUp 0.5s ease;
}
.home-tesla-mark {
    color: #cc2b32;
    font-size: clamp(0.85rem, 2.6vh, 1.15rem);
    font-weight: 800;
    letter-spacing: 0.45em;
    text-shadow: 0 0 14px rgba(204,43,50,0.5);
    font-family: "SF Mono", "Menlo", monospace;
}
.home-pill {
    background: rgba(40,40,42,0.85);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 999px;
    padding: clamp(0.2rem, 0.8vh, 0.35rem) clamp(0.5rem, 2vw, 0.8rem);
    font-size: clamp(0.65rem, 1.8vh, 0.82rem);
    font-weight: 500;
    display: flex; align-items: center; gap: 0.35rem;
}
.home-pill .reddot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #cc2b32;
    animation: pulseRedDot 2s ease infinite;
}

/* hero 區 — 給最多空間，但有限度 */
.home-hero {
    flex: 2 1 auto;
    position: relative;
    margin: 0 calc(-1 * clamp(0.8rem, 4vw, 1.25rem));
    min-height: 0;
    max-height: 34vh;
    overflow: hidden;
    background:
        radial-gradient(ellipse at 30% 20%, rgba(80,30,35,0.4) 0%, transparent 50%),
        radial-gradient(ellipse at 70% 30%, rgba(120,50,60,0.3) 0%, transparent 50%),
        linear-gradient(180deg, #2a1a1f 0%, #0a0a0c 70%, #000 100%);
}
.home-hero::before {
    content: "";
    position: absolute;
    inset: 0;
    background-image:
        linear-gradient(180deg, transparent 0%, transparent 50%, rgba(0,0,0,0.8) 100%),
        repeating-linear-gradient(90deg,
            transparent 0px, transparent 12px,
            rgba(20,25,35,0.6) 12px, rgba(20,25,35,0.6) 14px,
            transparent 14px, transparent 28px,
            rgba(30,35,45,0.5) 28px, rgba(30,35,45,0.5) 32px);
    background-position: 0 60%;
    background-size: 100% 50%;
    background-repeat: no-repeat;
    opacity: 0.55;
}
.home-hero img {
    position: absolute;
    bottom: 6%;
    left: 50%;
    transform: translateX(-50%);
    max-width: 100%;
    max-height: 90%;
    width: auto;
    height: auto;
    object-fit: contain;
    filter: drop-shadow(0 16px 24px rgba(0,0,0,0.85));
    animation: carFloat 4s ease-in-out infinite 0.5s;
}

/* MODEL 3 標籤 */
.home-model-label {
    flex: 0 0 auto;
    text-align: center;
    animation: fadeInUp 0.6s ease 0.2s both;
}
.home-model-name {
    font-size: clamp(0.95rem, 2.4vh, 1.3rem);
    font-weight: 300;
    letter-spacing: 0.55em;
    margin-right: -0.55em;
    color: #f3f5f7;
    font-family: "SF Mono", monospace;
}
.home-model-sub {
    font-size: clamp(0.58rem, 1.4vh, 0.72rem);
    letter-spacing: 0.25em;
    color: #8a8e93;
    margin-top: 0.4vh;
    margin-right: -0.25em;
}
.home-model-divider {
    width: 36px; height: 2px;
    background: #cc2b32;
    margin: 0.6vh auto 0;
    border-radius: 1px;
}

/* Welcome/Angela */
.home-welcome {
    flex: 0 0 auto;
    animation: fadeInUp 0.6s ease 0.4s both;
}
.home-welcome-label {
    font-size: clamp(0.78rem, 1.9vh, 0.95rem);
    color: #f3f5f7;
    font-weight: 400;
    line-height: 1.2;
}
.home-name {
    font-size: clamp(2.0rem, 6vh, 2.7rem);
    font-weight: 700;
    line-height: 1.15;
    padding-bottom: 0.15rem;
    background: linear-gradient(135deg, #ff6b76 0%, #cc2b32 60%, #8a1d23 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
    display: inline-block;
}
.home-name-underline {
    width: 44px; height: 2px;
    background: #cc2b32;
    margin-top: 0.3vh;
}
.home-tagline {
    flex: 0 0 auto;
    color: #a8acb1;
    font-size: clamp(0.7rem, 1.7vh, 0.85rem);
    line-height: 1.4;
    margin-top: 0.6vh;
    animation: fadeInUp 0.6s ease 0.55s both;
}

/* 卡片 */
.home-cards {
    flex: 0 0 auto;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: clamp(0.5rem, 2vw, 0.8rem);
    margin-top: 0.8vh;
    animation: fadeInUp 0.6s ease 0.7s both;
}
.home-card {
    position: relative;
    background:
        radial-gradient(ellipse at 50% 30%, rgba(204,43,50,0.15) 0%, transparent 60%),
        rgba(30,30,32,0.6);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: clamp(0.5rem, 1.4vh, 0.9rem) 0.5rem;
    text-align: center;
    overflow: hidden;
}
.home-card-icon {
    font-size: clamp(1.3rem, 3.6vh, 1.9rem);
    margin-bottom: 0.3vh;
    display: inline-block;
    filter: drop-shadow(0 0 10px rgba(204,43,50,0.4));
}
.home-card-title {
    font-size: clamp(0.82rem, 1.9vh, 0.95rem);
    font-weight: 600;
    color: #f3f5f7;
    margin-bottom: 0.1rem;
}
.home-card-sub {
    font-size: clamp(0.62rem, 1.4vh, 0.72rem);
    color: #8a8e93;
}
.home-card::after {
    content: "";
    position: absolute;
    bottom: 0; left: 50%;
    transform: translateX(-50%);
    width: 40%; height: 2px;
    background: linear-gradient(90deg, transparent, #cc2b32, transparent);
    box-shadow: 0 0 8px #cc2b32;
}

/* 進入按鈕 — 用 a 標籤，是 .tesla-home 的子元素 */
.home-enter-btn {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    margin-top: 0.8vh;
    padding: clamp(0.75rem, 1.8vh, 1.05rem) 1rem;
    background: linear-gradient(135deg, #d93340 0%, #cc2b32 50%, #a52229 100%);
    color: #fff !important;
    border: none;
    border-radius: 999px;
    font-size: clamp(0.88rem, 2vh, 1rem);
    font-weight: 600;
    letter-spacing: 0.02em;
    box-shadow: 0 6px 20px rgba(204,43,50,0.4), 0 0 24px rgba(204,43,50,0.18);
    text-decoration: none !important;
    cursor: pointer;
    animation: fadeInUp 0.6s ease 0.85s both;
    box-sizing: border-box;
    min-height: clamp(44px, 6vh, 56px);
    transition: transform 0.15s ease;
}
.home-enter-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 28px rgba(204,43,50,0.55), 0 0 32px rgba(204,43,50,0.3);
}
.home-enter-btn .arrow {
    margin-left: 0.5rem;
    font-weight: 400;
}

/* ===== 小尺寸 iPhone（SE、mini）特別調整 ===== */
@media (max-height: 670px) {
    .tesla-home { gap: 0.2vh; padding-top: 0.3rem; padding-bottom: 0.3rem; }
    .home-hero { max-height: 28vh; }
    .home-model-label { display: none; }  /* SE 上太擠就藏起 MODEL 3 標籤 */
    .home-card { padding: 0.5rem; }
    .home-card-icon { font-size: 1.3rem; }
    .home-tagline { line-height: 1.3; }
}
/* 超小尺寸 (<= 580px 高) */
@media (max-height: 580px) {
    .home-hero { max-height: 24vh; }
    .home-cards { gap: 0.4rem; }
}
</style>
"""

    html_parts = [
        '<div class="tesla-home">',
        '<div class="home-topbar">',
        '<div class="home-tesla-mark">T E S L A</div>',
        '<div class="home-pill"><span class="reddot"></span><span>Model 3</span></div>',
        '</div>',
        '<div class="home-hero">',
        f'<img src="{car_uri}" alt="Tesla Model 3 Midnight Silver Metallic"/>',
        '</div>',
        '<div class="home-model-label">',
        '<div class="home-model-name">MODEL&nbsp;3</div>',
        '<div class="home-model-sub">MIDNIGHT SILVER METALLIC</div>',
        '<div class="home-model-divider"></div>',
        '</div>',
        '<div class="home-welcome">',
        '<div class="home-welcome-label">Welcome,</div>',
        '<div class="home-name">Angela</div>',
        '<div class="home-name-underline"></div>',
        '</div>',
        '<div class="home-tagline">Your Model 3. Your Journey.<br/>All in One Place.</div>',
        '<div class="home-cards">',
        '<div class="home-card">',
        '<div class="home-card-icon">🔋</div>',
        '<div class="home-card-title">Battery Health</div>',
        '<div class="home-card-sub">Smart Tracking</div>',
        '</div>',
        '<div class="home-card">',
        '<div class="home-card-icon">📈</div>',
        '<div class="home-card-title">Driving Insights</div>',
        '<div class="home-card-sub">Trend Analysis</div>',
        '</div>',
        '</div>',
        # 進入按鈕 — 直接是 .tesla-home 的子元素
        '<a href="?enter=1" class="home-enter-btn" target="_self">'
        "Enter Angela's Model 3 <span class=\"arrow\">→</span>"
        '</a>',
        '</div>',
    ]
    html = "".join(html_parts)

    st.markdown(css, unsafe_allow_html=True)
    st.markdown(html, unsafe_allow_html=True)


def _render_loading_page():
    """Loading 畫面 — 動畫車身 + 進度條，2.5 秒後自動進入主 app。"""
    car_uri = _img_to_data_uri(os.path.join(_HERE, "assets", "model3_real.jpg"))

    LOADING_DURATION = 2.8
    elapsed = time.time() - st.session_state.get("loading_started_at", time.time())
    progress = min(1.0, elapsed / LOADING_DURATION)
    pct = int(progress * 100)

    css = """
<style>
[data-testid="stHeader"] { background: transparent !important; }
#MainMenu, footer { visibility: hidden; }
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}
[data-testid="stAppViewContainer"] > .main { background: #000 !important; }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes carDrive {
    0%   { transform: translateX(calc(-50% - 25px)) scale(0.95); filter: brightness(0.85); }
    50%  { transform: translateX(-50%) scale(1);    filter: brightness(1); }
    100% { transform: translateX(calc(-50% + 25px)) scale(1.04); filter: brightness(1.1); }
}
@keyframes lightStreaks {
    0%   { background-position: 100% 35%, -50% 50%, 30% 65%, 50% 50%; opacity: 0; }
    20%  { opacity: 1; }
    100% { background-position: -200% 35%, 200% 50%, -100% 65%, 50% 50%; opacity: 1; }
}

.tesla-loading {
    background: #000;
    min-height: 100vh;
    color: #f3f5f7;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", system-ui, sans-serif;
    max-width: 430px;
    margin: 0 auto;
    padding: 4rem 1.5rem 3rem;
    position: relative;
    overflow: hidden;
    animation: fadeIn 0.5s ease;
}
.loading-tesla-mark {
    color: #cc2b32;
    font-size: 1.6rem;
    font-weight: 800;
    letter-spacing: 0.5em;
    text-shadow: 0 0 18px rgba(204,43,50,0.6);
    font-family: "SF Mono", "Menlo", monospace;
    text-align: center;
    margin-bottom: 2rem;
}
.loading-title {
    text-align: center;
    font-size: 1rem;
    letter-spacing: 0.18em;
    color: #f3f5f7;
    margin-bottom: 0.6rem;
}
.loading-subtitle {
    text-align: center;
    font-size: 0.85rem;
    color: #8a8e93;
    margin-bottom: 3rem;
}
.loading-stage {
    position: relative;
    height: 280px;
    margin: 0 -1.5rem 3rem;
    background:
        linear-gradient(90deg, transparent 0%, transparent 70%, rgba(204,43,50,0.6) 85%, transparent 100%),
        linear-gradient(90deg, transparent 0%, transparent 60%, rgba(204,43,50,0.4) 80%, transparent 100%),
        linear-gradient(90deg, transparent 0%, transparent 65%, rgba(204,43,50,0.5) 78%, transparent 100%),
        radial-gradient(ellipse at center, #1a1a1f 0%, #000 80%);
    background-size: 200% 4px, 200% 3px, 200% 5px, 100% 100%;
    background-position: 100% 35%, -50% 50%, 30% 65%, 50% 50%;
    background-repeat: no-repeat;
    animation: lightStreaks 3s linear infinite;
}
.loading-stage img {
    position: absolute;
    bottom: 0;
    left: 50%;
    width: 100%;
    max-width: 460px;
    transform: translateX(-50%);
    filter: drop-shadow(0 25px 35px rgba(0,0,0,0.9)) drop-shadow(0 0 30px rgba(204,43,50,0.2));
    animation: carDrive 1.6s ease-in-out infinite alternate;
}
.loading-progress-wrap { position: relative; margin-top: 2rem; }
.loading-progress-track {
    height: 3px;
    background: rgba(255,255,255,0.1);
    border-radius: 2px;
    overflow: hidden;
    position: relative;
}
.loading-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #cc2b32, #ff6b76);
    border-radius: 2px;
    width: __PCT__%;
    transition: width 0.3s ease;
    box-shadow: 0 0 12px rgba(204,43,50,0.7);
}
.loading-pct {
    text-align: center;
    margin-top: 1.2rem;
    font-size: 1.05rem;
    color: #f3f5f7;
    font-weight: 400;
    letter-spacing: 0.06em;
}
</style>
""".replace("__PCT__", str(pct))

    html_parts = [
        '<div class="tesla-loading">',
        '<div class="loading-tesla-mark">T E S L A</div>',
        '<div class="loading-title">CONNECTING TO YOUR MODEL 3</div>',
        '<div class="loading-subtitle">Preparing your vehicle data&hellip;</div>',
        '<div class="loading-stage">',
        f'<img src="{car_uri}" alt="Tesla Model 3"/>',
        '</div>',
        '<div class="loading-progress-wrap">',
        '<div class="loading-progress-track">',
        '<div class="loading-progress-fill"></div>',
        '</div>',
        f'<div class="loading-pct">{pct}%</div>',
        '</div>',
        '</div>',
    ]
    html = "".join(html_parts)

    st.markdown(css, unsafe_allow_html=True)
    st.markdown(html, unsafe_allow_html=True)

    if progress < 1.0:
        time.sleep(0.3)
        st.rerun()
    else:
        st.session_state.page = "main"
        st.rerun()


# ====================================================================
# Page state machine
# ====================================================================
if "page" not in st.session_state:
    st.session_state.page = "home"

if st.session_state.page == "home":
    _render_home_page()
    st.stop()

if st.session_state.page == "loading":
    _render_loading_page()
    st.stop()


# 否則進入主 app — 後續是原本的監測 UI
# ----------------------------------------------------------------
inject_mobile_css()


# ---------- 頂部標題 ----------
st.markdown(
    """
    <div class="app-header">
        <div class="app-title">🔋 Tesla 充電健康監測</div>
        <div class="app-sub">電池健康<em>代理</em>分析</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- 分頁 ----------
# 短標籤 + emoji 一律配 1 個全形空格，避免 iPhone 直拿時重疊
TAB_NAMES = [
    "📷 新增",
    "📊 總覽",
    "🔁 比較",
    "⚖️ 控制",
    "❤️ 健康",
    "📝 報告",
    "🗂️ 資料",
]
tabs = st.tabs(TAB_NAMES)


# =====================================================================
# 分頁 1 — 新增資料
# =====================================================================
with tabs[0]:
    section_header("新增充電紀錄")

    # ---- 狀態初始化 ----
    # ⭐ 重要：number_input 的值直接放在 widget 自己的 key（odometer / battery_start），
    # 這樣 OCR 確認後寫回 session_state 就能立刻反映在 input 欄位上。
    #
    # 💡 處理「OCR 確認帶入」與「儲存後重設」— 必須在 widget render 之前執行
    # 因為 Streamlit 不允許在 widget 已 instantiated 之後直接寫 widget key

    # 1. OCR 確認後要帶入的值（從 modal 那邊放進 pending dict）
    if "pending_ocr_values" in st.session_state:
        pending = st.session_state.pop("pending_ocr_values")
        st.session_state.odometer = pending.get("odometer", 0.0)
        st.session_state.battery_start = pending.get("battery_start", 20)

    # 2. 儲存後要清空輸入欄位
    if st.session_state.get("reset_inputs_on_next_run"):
        st.session_state.odometer = 0.0
        st.session_state.battery_start = 20
        st.session_state.reset_inputs_on_next_run = False

    # 3. 🆕 儲存後要清掉上傳/拍照 widget 的內容
    # Streamlit 不允許直接寫 widget key，所以用 nonce 動態改變 widget key —
    # 等於建立全新的 widget，自然就「沒有檔案」了
    if "uploader_nonce" not in st.session_state:
        st.session_state.uploader_nonce = 0
    if st.session_state.get("reset_uploader_on_next_run"):
        st.session_state.uploader_nonce += 1
        st.session_state.reset_uploader_on_next_run = False

    if "odometer" not in st.session_state:
        st.session_state.odometer = 0.0
    if "battery_start" not in st.session_state:
        st.session_state.battery_start = 20
    if "ocr_confirmed" not in st.session_state:
        st.session_state.ocr_confirmed = False
    if "ocr_confidence" not in st.session_state:
        st.session_state.ocr_confidence = 0.0
    if "ocr_notes" not in st.session_state:
        st.session_state.ocr_notes = ""
    # 暫存 OCR 偵測到的原始值，供 modal 預填
    if "ocr_detected" not in st.session_state:
        st.session_state.ocr_detected = {
            "odometer_miles": None, "start_battery_pct": None,
            "confidence": 0.0, "notes": "",
        }
    if "temp_photo_path" not in st.session_state:
        st.session_state.temp_photo_path = None
    if "show_confirm_dialog" not in st.session_state:
        st.session_state.show_confirm_dialog = False
    if "gemini_api_key" not in st.session_state:
        st.session_state.gemini_api_key = ""

    capture_mode = st.radio(
        "輸入方式",
        ["📷 拍照 / 上傳 (Gemini Vision)", "✏️ 手動輸入"],
        horizontal=False,
        key="capture_mode_radio",
    )

    charging_date = st.date_input(
        "充電日期",
        value=get_user_today(),
        format="MM/DD/YYYY",
        key="charging_date_input",
    )
    # 顯示固定時區（Los Angeles）下的今日
    st.caption(f"🌐 時區：**Los Angeles**　・　今日：**{get_user_today().isoformat()}**")

    final_battery_pct = st.slider(
        "結束時電量 %",
        min_value=0, max_value=100, value=80, step=1,
        key="final_battery_pct",
    )

    # ----- 模式 A：照片 / OCR -----
    if capture_mode.startswith("📷"):
        # ----- Gemini API Key 設定 -----
        from modules.ocr_extractor import has_api_key as _has_key
        env_has_key = _has_key()

        with st.expander(
            "🔑 Gemini API Key " + ("（已從環境讀取）" if env_has_key else "（必填）"),
            expanded=not env_has_key,
        ):
            st.markdown(
                "若您在 `.streamlit/secrets.toml` 或環境變數中已設定 "
                "`GEMINI_API_KEY`，則此處可留空。"
                "否則請在下方貼上 API Key（不會儲存於程式碼，僅存於目前 session）。\n\n"
                "🔗 [取得 Gemini API Key](https://aistudio.google.com/apikey)"
            )
            api_key_input = st.text_input(
                "Gemini API Key",
                value=st.session_state.gemini_api_key,
                type="password",
                key="gemini_api_key_input",
                placeholder="貼上 API Key…",
            )
            if api_key_input != st.session_state.gemini_api_key:
                st.session_state.gemini_api_key = api_key_input

        st.markdown("##### 照片來源")
        source_choice = st.radio(
            "選擇照片來源：",
            ["上傳照片", "拍照"],
            horizontal=True,
            key="source_choice",
        )

        image_bytes = None
        source_type = "manual"

        # 動態 key — 儲存後 nonce 會 +1，等於 widget 重新生成 → 自動清空檔案
        _nonce = st.session_state.uploader_nonce
        _uploader_key = f"uploader_{_nonce}"
        _camera_key = f"camera_{_nonce}"

        if source_choice == "上傳照片":
            uploaded = st.file_uploader(
                "上傳 Tesla 儀表板照片",
                type=["jpg", "jpeg", "png", "webp"],
                key=_uploader_key,
            )
            if uploaded is not None:
                image_bytes = uploaded.getvalue()
                source_type = "upload"
        else:
            camera = st.camera_input("拍下 Tesla 儀表板", key=_camera_key)
            if camera is not None:
                image_bytes = camera.getvalue()
                source_type = "camera"

        st.caption(
            "ℹ️ 本 App 使用 **Google Gemini Vision** 辨識照片中的里程與電量。"
        )

        if image_bytes is not None:
            temp_name = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            temp_path = os.path.join(TEMP_DIR, temp_name)
            with open(temp_path, "wb") as f:
                f.write(image_bytes)
            st.session_state.temp_photo_path = temp_path

            st.image(image_bytes, caption="預覽", use_column_width=True)

            if st.button("🔍 用 Gemini 擷取數值", use_container_width=True,
                         type="primary"):
                with st.spinner("Gemini 辨識中..."):
                    result = extract_from_image(
                        temp_path,
                        backend="gemini",
                        api_key=st.session_state.gemini_api_key or None,
                    )
                # 把 OCR 結果暫存在獨立的 dict（不要碰 widget 的 key）
                st.session_state.ocr_detected = result
                if result.get("confidence", 0) > 0:
                    # 觸發確認對話框
                    st.session_state.show_confirm_dialog = True
                    st.rerun()
                else:
                    st.error(result.get("notes", "無法自動擷取，請手動輸入。"))
    else:
        # 手動模式 — 不動 widget key，使用者可以直接編輯下方欄位
        source_type = "manual"
        st.info("✏️ 手動模式 — 不需要照片，直接填入下方欄位即可。")

    # =================================================================
    # ⭐ Gemini OCR 完成後彈出確認對話框
    # =================================================================
    if st.session_state.show_confirm_dialog:
        ext = st.session_state.ocr_detected  # 從暫存的偵測結果讀

        @st.dialog("✅ 確認辨識結果")
        def _confirm_dialog():
            st.markdown(
                f"Gemini 從照片辨識出以下數值（信心度 "
                f"**{ext.get('confidence', 0):.0%}**）。\n\n"
                "**請確認數值是否正確**，若有錯誤可直接編輯，再按下「確認並帶入」。"
            )

            if ext.get("notes"):
                st.caption(f"📝 Gemini 備註：{ext['notes']}")

            col_a, col_b = st.columns(2)
            with col_a:
                dlg_odo = st.number_input(
                    "里程 (miles)",
                    min_value=0.0, max_value=999999.0,
                    value=float(ext.get("odometer_miles") or 0.0),
                    step=1.0,
                    key="dlg_odo",
                    help="請與儀表板上的里程數核對。",
                )
            with col_b:
                dlg_sb = st.number_input(
                    "起始電量 %",
                    min_value=0, max_value=100,
                    value=int(ext.get("start_battery_pct") or 0),
                    step=1,
                    key="dlg_sb",
                    help="請與儀表板上的電量百分比核對。",
                )

            st.markdown("---")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("✅ 確認並帶入",
                             use_container_width=True, type="primary",
                             key="dlg_confirm"):
                    # ⭐ 不能直接寫 st.session_state["odometer"] — widget 已被 instantiated
                    # 改用 pending dict，下次 rerun 在 widget 之前才套用
                    st.session_state["pending_ocr_values"] = {
                        "odometer": float(dlg_odo),
                        "battery_start": int(dlg_sb),
                    }
                    st.session_state["ocr_confirmed"] = True
                    st.session_state["ocr_confidence"] = float(ext.get("confidence", 0.0) or 0.0)
                    st.session_state["ocr_notes"] = ext.get("notes", "")
                    st.session_state.show_confirm_dialog = False
                    st.toast(
                        f"✅ 已帶入：里程 {float(dlg_odo):,.0f}, 起始電量 {int(dlg_sb)}%",
                        icon="✅",
                    )
                    st.rerun()
            with col_btn2:
                if st.button("❌ 取消，重新辨識",
                             use_container_width=True, key="dlg_cancel"):
                    # 取消：清除 OCR 偵測結果，但不動 widget keys
                    st.session_state.ocr_detected = {
                        "odometer_miles": None, "start_battery_pct": None,
                        "confidence": 0.0, "notes": "",
                    }
                    st.session_state.show_confirm_dialog = False
                    st.rerun()

        _confirm_dialog()

    # ----- 共用：審閱 / 編輯數值 + 儲存 -----
    st.markdown("##### 確認 / 輸入數值")
    if st.session_state.get("ocr_confirmed"):
        st.success(
            f"📷 已從照片帶入數值（Gemini 信心度 "
            f"{st.session_state.get('ocr_confidence', 0):.0%}）— "
            "您仍可手動編輯下方欄位，再按「確認儲存」。"
        )
    col1, col2 = st.columns(2)
    with col1:
        # ⭐ 不傳 value=，只用 key — Streamlit 會直接讀 st.session_state.odometer
        # 這樣 OCR 確認後寫入 st.session_state.odometer 才會立刻顯示在 input 裡
        odometer_miles = st.number_input(
            "里程 (miles)",
            min_value=0.0, max_value=999999.0,
            step=1.0,
            format="%.1f",
            key="odometer",
        )
    with col2:
        start_battery_pct = st.number_input(
            "起始電量 %",
            min_value=0, max_value=100,
            step=1,
            key="battery_start",
        )

    confidence = float(st.session_state.get("ocr_confidence", 0.0) or 0.0)
    notes = st.session_state.get("ocr_notes", "")
    if notes and confidence == 0:
        st.caption(f"OCR 訊息：{notes}")

    # ----- 驗證 -----
    warnings_list = []
    df_now = load_df()
    if not df_now.empty:
        df_sorted = df_now.sort_values(["charging_date", "created_at"])
        prev_odo = df_sorted["odometer_miles"].iloc[-1]
        miles_diff_preview = odometer_miles - prev_odo
        if miles_diff_preview < 0:
            warnings_list.append(
                f"⚠️ 里程 ({odometer_miles:,.0f}) 小於前一筆 ({prev_odo:,.0f})，請確認。"
            )
        else:
            st.caption(f"距離上次充電里程：**{miles_diff_preview:,.1f}**")

    bpa_preview = final_battery_pct - start_battery_pct
    if bpa_preview < 0:
        warnings_list.append(
            f"⚠️ 結束電量 ({final_battery_pct}%) 小於起始電量 ({start_battery_pct}%)，請確認。"
        )
    else:
        st.caption(f"此次增加電量：**{bpa_preview}%**")

    for w in warnings_list:
        st.warning(w)

    manual_verified = st.checkbox("我已確認以上數值正確",
                                  value=False, key="manual_verified")

    save_disabled = (not manual_verified) or (len(warnings_list) > 0)
    if st.button("💾 確認儲存", use_container_width=True,
                 disabled=save_disabled, type="primary"):
        record = {
            "charging_date": charging_date.isoformat(),
            "odometer_miles": float(odometer_miles),
            "start_battery_pct": int(start_battery_pct),
            "final_battery_pct": int(final_battery_pct),
            "source_type": source_type,
            "ocr_confidence": confidence,
            "manual_verified": bool(manual_verified),
        }
        store.append(record)

        # 刪除暫存照片
        if st.session_state.temp_photo_path and os.path.exists(st.session_state.temp_photo_path):
            try:
                os.remove(st.session_state.temp_photo_path)
            except Exception:
                pass
        cleanup_temp_files()

        st.session_state.temp_photo_path = None
        # 重設 OCR 相關狀態
        st.session_state.ocr_detected = {
            "odometer_miles": None, "start_battery_pct": None,
            "confidence": 0.0, "notes": "",
        }
        st.session_state.ocr_confirmed = False
        st.session_state.ocr_confidence = 0.0
        st.session_state.ocr_notes = ""
        # ⚠️ 不能直接寫 st.session_state.odometer = 0.0（widget 已 instantiated）
        # 改用 flag，下次 rerun 在 widget 之前才重設
        st.session_state.reset_inputs_on_next_run = True
        # 🆕 同時要求清掉上傳/拍照 widget 的內容（透過 nonce 換 key）
        st.session_state.reset_uploader_on_next_run = True

        st.success("✅ 紀錄已儲存。暫存照片已刪除。儀表板已更新。")
        st.balloons()
        st.rerun()


# =====================================================================
# 分頁 2 — 總覽儀表板
# =====================================================================
with tabs[1]:
    section_header("總覽儀表板")

    df = load_df()
    if df.empty:
        st.info("尚無紀錄。請至「**新增**」分頁新增第一筆紀錄，或至「**資料**」分頁匯入 Excel。")
    else:
        kpis = overview_kpis(df)

        row1 = st.columns(2)
        with row1[0]: kpi_card("總紀錄數", f"{kpis['total_records']:,}")
        with row1[1]: kpi_card("平均充電間隔里程", f"{kpis['avg_miles_diff']:,.1f}")

        row2 = st.columns(2)
        with row2[0]: kpi_card("間隔里程中位數", f"{kpis['median_miles_diff']:,.1f}")
        with row2[1]: kpi_card("最長間隔里程", f"{kpis['max_miles_diff']:,.1f}")

        row3 = st.columns(2)
        with row3[0]: kpi_card("平均起始電量", f"{kpis['avg_start_battery_pct']:.1f}%")
        with row3[1]: kpi_card("平均結束電量", f"{kpis['avg_final_battery_pct']:.1f}%")

        row4 = st.columns(2)
        with row4[0]: kpi_card("平均增加電量", f"{kpis['avg_battery_pct_added']:.1f}%")
        with row4[1]: kpi_card("最低起始電量", f"{kpis['min_start_battery_pct']:.0f}%")

        row5 = st.columns(2)
        with row5[0]: kpi_card("低電量充電次數", f"{kpis['low_battery_count']:,}")
        with row5[1]: kpi_card("低電量充電比例", f"{kpis['low_battery_rate']*100:.1f}%")

        st.divider()

        st.plotly_chart(chart_count_by_year(df), use_container_width=True, config=plotly_static_config())
        st.plotly_chart(chart_avg_miles_diff_by_year(df), use_container_width=True, config=plotly_static_config())
        st.plotly_chart(chart_avg_start_battery_by_year(df), use_container_width=True, config=plotly_static_config())
        st.plotly_chart(chart_avg_final_battery_by_year(df), use_container_width=True, config=plotly_static_config())
        st.plotly_chart(chart_battery_added_over_time(df), use_container_width=True, config=plotly_static_config())
        st.plotly_chart(chart_odometer_trend(df), use_container_width=True, config=plotly_static_config())
        st.plotly_chart(chart_monthly_frequency(df), use_container_width=True, config=plotly_static_config())


# =====================================================================
# 分頁 3 — 時段比較（下拉選單）
# =====================================================================
with tabs[2]:
    section_header("時段比較")

    df = load_df()
    if df.empty:
        st.info("尚無紀錄，請先匯入或新增資料。")
    else:
        # 改成下拉選單
        modules_list = [
            ("依年份", "year"),
            ("依季", "year_quarter"),
            ("依月", "year_month"),
            ("依週", "year_week"),
            ("依日", "charging_date"),
            ("依季節", "season_year_label"),
            ("同月跨年比較", "same_month_years"),
            ("同季節跨年比較", "same_season_years"),
            ("冬季跨年比較", "winter_years"),
            ("同週跨年比較", "same_week_years"),
            ("同一年不同月份", "same_year_months"),
            ("同一月不同週", "same_month_weeks"),
            ("同一週不同日", "same_week_days"),
        ]

        labels = [label for label, _ in modules_list]
        keys = {label: key for label, key in modules_list}

        selected_label = st.selectbox("選擇比較方式", labels, key="cmp_select")
        active = keys[selected_label]

        st.divider()

        metric_label = st.selectbox("分析指標", list(metric_options().keys()))
        metric_key = metric_options()[metric_label]

        # 將篩選狀態存到 session（供報告分頁使用）
        st.session_state["report_compare_filter"] = {
            "module_key": active,
            "module_label": selected_label,
            "metric_key": metric_key,
            "metric_label": metric_label,
            "sub_value": None,
            "sub_value_label": None,
        }

        # 簡單聚合
        simple_map = {
            "year": ("year", "年份"),
            "year_quarter": ("year_quarter", "季"),
            "year_month": ("year_month", "月"),
            "year_week": ("year_week", "週"),
            "charging_date": ("charging_date", "日"),
            "season_year_label": ("season_year_label", "季節"),
        }

        if active in simple_map:
            group_col, axis_label = simple_map[active]
            agg = aggregate(df, group_col)
            if agg.empty:
                st.warning("資料不足。")
            else:
                fig = chart_aggregate(agg, group_col, metric_key, axis_label, metric_label)
                st.plotly_chart(fig, use_container_width=True, config=plotly_static_config())
                with st.expander("顯示原始資料"):
                    st.dataframe(agg, use_container_width=True)

        elif active == "same_month_years":
            month = st.selectbox("選擇月份", list(range(1, 13)),
                                 format_func=lambda m: f"{m:02d} 月")
            st.session_state["report_compare_filter"]["sub_value"] = month
            st.session_state["report_compare_filter"]["sub_value_label"] = f"{month:02d} 月"
            cmp_df = same_period_across_years(df, "month", month)
            if cmp_df.empty:
                st.warning("該月份無跨年資料。")
            else:
                fig = chart_same_period_across_years(cmp_df, metric_key,
                                                     f"{metric_label} — {month:02d} 月")
                st.plotly_chart(fig, use_container_width=True, config=plotly_static_config())
                with st.expander("顯示原始資料"):
                    st.dataframe(cmp_df, use_container_width=True)

        elif active == "same_season_years":
            season_options = {"春季": "Spring", "夏季": "Summer", "秋季": "Fall", "冬季": "Winter"}
            season_label = st.selectbox("選擇季節", list(season_options.keys()))
            season = season_options[season_label]
            st.session_state["report_compare_filter"]["sub_value"] = season_label
            st.session_state["report_compare_filter"]["sub_value_label"] = season_label
            cmp_df = same_period_across_years(df, "season", season)
            if cmp_df.empty:
                st.warning("該季節無跨年資料。")
            else:
                fig = chart_same_period_across_years(cmp_df, metric_key,
                                                     f"{metric_label} — {season_label}")
                st.plotly_chart(fig, use_container_width=True, config=plotly_static_config())
                with st.expander("顯示原始資料"):
                    st.dataframe(cmp_df, use_container_width=True)

        elif active == "winter_years":
            cmp_df = same_period_across_years(df, "season", "Winter")
            if cmp_df.empty:
                st.warning("無冬季資料。")
            else:
                fig = chart_same_period_across_years(cmp_df, metric_key,
                                                     f"{metric_label} — 冬季")
                st.plotly_chart(fig, use_container_width=True, config=plotly_static_config())
                with st.expander("顯示原始資料"):
                    st.dataframe(cmp_df, use_container_width=True)

        elif active == "same_week_years":
            weeks = sorted(df["week_number"].dropna().unique().tolist())
            if not weeks:
                st.warning("無可用週數。")
            else:
                week = st.selectbox("選擇 ISO 週數", weeks)
                st.session_state["report_compare_filter"]["sub_value"] = week
                st.session_state["report_compare_filter"]["sub_value_label"] = f"第 {week} 週"
                cmp_df = same_period_across_years(df, "week_number", week)
                if cmp_df.empty:
                    st.warning("該週無跨年資料。")
                else:
                    fig = chart_same_period_across_years(cmp_df, metric_key,
                                                         f"{metric_label} — 第 {week} 週")
                    st.plotly_chart(fig, use_container_width=True, config=plotly_static_config())
                    with st.expander("顯示原始資料"):
                        st.dataframe(cmp_df, use_container_width=True)

        elif active == "same_year_months":
            years = sorted(df["year"].unique().tolist())
            if not years:
                st.warning("無可用年份。")
            else:
                year = st.selectbox("選擇年份", years)
                sub = df[df["year"] == year]
                agg = aggregate(sub, "month")
                if agg.empty:
                    st.warning("無資料。")
                else:
                    fig = chart_aggregate(agg, "month", metric_key, "月份", metric_label)
                    st.plotly_chart(fig, use_container_width=True, config=plotly_static_config())
                    with st.expander("顯示原始資料"):
                        st.dataframe(agg, use_container_width=True)

        elif active == "same_month_weeks":
            year = st.selectbox("選擇年份", sorted(df["year"].unique().tolist()))
            month = st.selectbox("選擇月份", list(range(1, 13)),
                                 format_func=lambda m: f"{m:02d} 月")
            sub = df[(df["year"] == year) & (df["month"] == month)]
            agg = aggregate(sub, "week_number")
            if agg.empty:
                st.warning("該月無資料。")
            else:
                fig = chart_aggregate(agg, "week_number", metric_key, "週數", metric_label)
                st.plotly_chart(fig, use_container_width=True, config=plotly_static_config())
                with st.expander("顯示原始資料"):
                    st.dataframe(agg, use_container_width=True)

        elif active == "same_week_days":
            year = st.selectbox("選擇年份", sorted(df["year"].unique().tolist()), key="swd_year")
            weeks = sorted(df[df["year"] == year]["week_number"].dropna().unique().tolist())
            if not weeks:
                st.warning("該年無可用週數。")
            else:
                week = st.selectbox("選擇 ISO 週", weeks, key="swd_week")
                sub = df[(df["year"] == year) & (df["week_number"] == week)]
                agg = aggregate(sub, "weekday")
                if agg.empty:
                    st.warning("該週無資料。")
                else:
                    fig = chart_aggregate(agg, "weekday", metric_key, "星期", metric_label)
                    st.plotly_chart(fig, use_container_width=True, config=plotly_static_config())
                    with st.expander("顯示原始資料"):
                        st.dataframe(agg, use_container_width=True)

        # ===== 季節定義說明（放在分頁最下方）=====
        st.divider()
        with st.expander("📖 季節定義（月份對照表）", expanded=False):
            st.markdown(
                """
                本 App 採用北半球氣候季節定義：

                | 季節 | 月份 |
                |---|---|
                | 🌸 **春季 (Spring)** | 3 月、4 月、5 月 |
                | ☀️ **夏季 (Summer)** | 6 月、7 月、8 月 |
                | 🍂 **秋季 (Fall)** | 9 月、10 月、11 月 |
                | ❄️ **冬季 (Winter)** | **12 月**、1 月、2 月 |

                **特別注意 — 冬季跨年處理：**

                冬季橫跨了年份（12 月屬於下一年的冬季），所以本 App 用 `season_year`
                來標示：

                - **2024 年 12 月** → 歸類為 **冬季 2025**
                - **2025 年 1 月、2 月** → 歸類為 **冬季 2025**
                - **2025 年 12 月** → 歸類為 **冬季 2026**

                這樣做可以讓「冬季跨年比較」正確地把同一個冬天的資料放在一起，
                而不是把 12 月跟隔年的 1、2 月切成兩半。
                """
            )


# =====================================================================
# 分頁 4 — 控制變數比較（季節調整）
# =====================================================================
with tabs[3]:
    section_header("控制變數比較")

    st.info(
        "🧪 **為什麼需要控制變數比較？** 充電行為會受到季節影響："
        "夏天開冷氣、冬天開暖氣與電池預熱都會大幅影響耗能。"
        "比較**同一季節/同月份/同季**跨年的資料，可以降低季節偏差。"
    )

    df = load_df()
    if df.empty:
        st.info("尚無紀錄。")
    else:
        mode = st.radio(
            "控制變數",
            ["同一季節跨年比較", "同月份跨年比較",
             "同季跨年比較", "氣候相近季節比較"],
            key="controlled_mode",
        )
        metric_label = st.selectbox("分析指標", list(metric_options().keys()),
                                    key="ctrl_metric")
        metric_key = metric_options()[metric_label]

        # 將篩選狀態存到 session（供報告分頁使用）
        st.session_state["report_controlled_filter"] = {
            "mode_label": mode,
            "metric_key": metric_key,
            "metric_label": metric_label,
            "sub_value": None,
            "sub_value_label": None,
        }

        st.caption(
            "ℹ️ 為了降低季節偏差，本比較固定**同季節/同月份/同季跨年**進行對照。"
        )

        if mode == "同一季節跨年比較":
            season_options = {"春季": "Spring", "夏季": "Summer",
                              "秋季": "Fall", "冬季": "Winter"}
            season_label = st.selectbox("季節", list(season_options.keys()),
                                        key="cs_season")
            season = season_options[season_label]
            st.session_state["report_controlled_filter"]["sub_value"] = season_label
            st.session_state["report_controlled_filter"]["sub_value_label"] = season_label
            cmp_df = same_period_across_years(df, "season", season)
            if cmp_df.empty:
                st.warning("無資料。")
            else:
                st.plotly_chart(
                    chart_same_period_across_years(cmp_df, metric_key,
                                                   f"{metric_label} — {season_label}"),
                    use_container_width=True,
                 config=plotly_static_config())
                st.dataframe(cmp_df, use_container_width=True)

        elif mode == "同月份跨年比較":
            month = st.selectbox("月份", list(range(1, 13)),
                                 format_func=lambda m: f"{m:02d} 月", key="cm_month")
            st.session_state["report_controlled_filter"]["sub_value"] = month
            st.session_state["report_controlled_filter"]["sub_value_label"] = f"{month:02d} 月"
            cmp_df = same_period_across_years(df, "month", month)
            if cmp_df.empty:
                st.warning("無資料。")
            else:
                st.plotly_chart(
                    chart_same_period_across_years(cmp_df, metric_key,
                                                   f"{metric_label} — {month:02d} 月"),
                    use_container_width=True,
                 config=plotly_static_config())
                st.dataframe(cmp_df, use_container_width=True)

        elif mode == "同季跨年比較":
            quarter = st.selectbox("季", [1, 2, 3, 4],
                                   format_func=lambda q: f"Q{q}", key="cq_q")
            st.session_state["report_controlled_filter"]["sub_value"] = quarter
            st.session_state["report_controlled_filter"]["sub_value_label"] = f"Q{quarter}"
            cmp_df = same_period_across_years(df, "quarter", quarter)
            if cmp_df.empty:
                st.warning("無資料。")
            else:
                st.plotly_chart(
                    chart_same_period_across_years(cmp_df, metric_key,
                                                   f"{metric_label} — Q{quarter}"),
                    use_container_width=True,
                 config=plotly_static_config())
                st.dataframe(cmp_df, use_container_width=True)

        else:  # 氣候相近季節（春+秋為溫和季節）
            st.caption("春季與秋季通常氣候相近（無極端冷熱）。")
            mild = df[df["season"].isin(["Spring", "Fall"])]
            if mild.empty:
                st.warning("無春/秋季資料。")
            else:
                agg = aggregate(mild, "season_year_label")
                st.plotly_chart(
                    chart_aggregate(agg, "season_year_label", metric_key,
                                    "溫和季節", metric_label),
                    use_container_width=True,
                 config=plotly_static_config())
                st.dataframe(agg, use_container_width=True)


# =====================================================================
# 分頁 5 — 電池健康代理分析
# =====================================================================
with tabs[4]:
    section_header("電池健康代理分析")
    st.caption(
        "⚠️ 這是基於里程與電量百分比行為的**代理（proxy）**分析，"
        "**不是**正式的 Tesla 電池診斷。"
    )

    df = load_df()
    if df.empty:
        st.info("尚無紀錄。")
    else:
        with st.expander("⚙️ 閾值設定（可調整）"):
            t = {}
            t["miles_diff_drop_pct"] = st.slider(
                "充電間隔里程下降警示 (%)", 5, 50,
                int(DEFAULT_THRESHOLDS["miles_diff_drop_pct"] * 100),
                key="rpt_t_miles_drop_raw",
            ) / 100.0
            t["low_battery_rate"] = st.slider(
                "低電量充電比例警示 (%)", 5, 80,
                int(DEFAULT_THRESHOLDS["low_battery_rate"] * 100),
                key="rpt_t_low_rate_raw",
            ) / 100.0
            t["low_battery_threshold_pct"] = st.slider(
                "低電量定義 (%)", 5, 40,
                DEFAULT_THRESHOLDS["low_battery_threshold_pct"],
                key="rpt_t_low_pct",
            )

        # 同步到 session_state 給報告分頁讀
        st.session_state["rpt_t_miles_drop"] = t["miles_diff_drop_pct"]
        st.session_state["rpt_t_low_rate"] = t["low_battery_rate"]
        # rpt_t_low_pct already saved by the slider's key

        summary = health_proxy_summary(df, thresholds=t)
        anomalies = detect_anomalies(df, thresholds=t)

        st.markdown("##### 指標總覽")
        for ind in summary["indicators"]:
            color = ind["status"]
            st.markdown(
                f'<div class="indicator-card {color}">'
                f'<div class="ind-title">{ind["title"]} {badge(color)}</div>'
                f'<div class="ind-detail">{ind["detail"]}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown("##### 異常偵測")
        if not anomalies:
            st.success("以目前閾值未偵測到異常行為。")
        else:
            for a in anomalies:
                color = a["severity"]
                st.markdown(
                    f'<div class="indicator-card {color}">'
                    f'<div class="ind-title">{a["title"]} {badge(color)}</div>'
                    f'<div class="ind-detail">{a["detail"]}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )


# =====================================================================
# 分頁 6 — 報告產生
# =====================================================================
with tabs[5]:
    section_header("綜合分析報告")

    df = load_df()
    if df.empty:
        st.info("尚無紀錄。請先匯入資料或新增充電紀錄。")
    else:
        # ----- 安全 import：避免 Streamlit Cloud 拿到舊版 module 而報錯 -----
        import importlib
        import sys as _sys_for_reload
        _collect_filter_state = None
        _render_report_in_app = None
        try:
            # 強制重新載入 module（繞過 Python import cache）
            if "modules.report_generator" in _sys_for_reload.modules:
                importlib.reload(_sys_for_reload.modules["modules.report_generator"])
            from modules.report_generator import collect_filter_state as _collect_filter_state
            from modules.report_generator import render_report_in_app as _render_report_in_app
        except ImportError as _e:
            st.error(
                f"❌ 報告產生器模組載入失敗：`{_e}`\n\n"
                "**可能原因**：Streamlit Cloud 仍在使用舊版本的 "
                "`modules/report_generator.py`。\n\n"
                "**解法**：\n"
                "1. 確認最新的 `modules/report_generator.py` 已 push 到 GitHub\n"
                "2. 到 Streamlit Cloud → Manage app → **Reboot app**\n"
                "3. 若仍失敗，到 Manage app → **Clear cache**，再 Reboot"
            )
            st.stop()

        # 從 session_state 讀取其他分頁的篩選
        filter_state = _collect_filter_state()

        st.markdown(
            "本報告會**自動彙整**您在以下四個分頁中所做的篩選與選擇，"
            "產生一份完整的分析報告："
        )

        # 顯示目前讀到的篩選狀態
        cmp_module = filter_state.get("compare_module") or "_尚未選擇_"
        ctrl_mode = filter_state.get("controlled_mode") or "_尚未選擇_"
        ctrl_detail = ""
        if filter_state.get("controlled_season") and "季節" in (filter_state.get("controlled_mode") or ""):
            ctrl_detail = f"（{filter_state['controlled_season']}）"
        elif filter_state.get("controlled_month") and "月份" in (filter_state.get("controlled_mode") or ""):
            ctrl_detail = f"（{filter_state['controlled_month']:02d} 月）"
        elif (filter_state.get("controlled_quarter") and
              "季" in (filter_state.get("controlled_mode") or "") and
              "季節" not in (filter_state.get("controlled_mode") or "")):
            ctrl_detail = f"（Q{filter_state['controlled_quarter']}）"

        health_custom = (
            filter_state.get("threshold_miles_drop") != 0.20 or
            filter_state.get("threshold_low_rate") != 0.30 or
            filter_state.get("threshold_low_pct") != 20
        )

        st.markdown(
            f"""
            - 📊 **總覽** — 全部資料 KPI 與趨勢圖（總覽分頁全部圖表）
            - 🔁 **比較** — {cmp_module}
            - ⚖️ **控制** — {ctrl_mode}{ctrl_detail}
            - ❤️ **健康** — {('已設自訂閾值' if health_custom else '使用預設閾值')}
            """
        )
        st.caption("💡 提示：先到「🔁 比較」、「⚖️ 控制」、「❤️ 健康」分頁挑好你要的篩選，再回來按下方按鈕。")

        st.divider()

        if st.button("📝 產生綜合報告", use_container_width=True, type="primary"):
            report_md = _render_report_in_app(df, filter_state)
            st.download_button(
                "⬇️ 下載報告 (.md)",
                report_md.encode("utf-8"),
                file_name=f"tesla_charging_report_{pd.Timestamp.now().strftime('%Y%m%d')}.md",
                mime="text/markdown",
                use_container_width=True,
            )


# =====================================================================
# 分頁 7 — 資料管理
# =====================================================================
with tabs[6]:
    section_header("資料管理")

    # ----- 顯示目前使用的儲存後端 -----
    if _STORE_BACKEND == "gsheets":
        st.success(
            "☁️ **使用 Google Sheets 儲存** — 資料會永久保存，"
            "即使 Streamlit Cloud 重啟也不會消失。"
        )
        ss_url = ""
        try:
            ss_url = st.secrets.get("gsheets", {}).get("spreadsheet_url", "")
        except Exception:
            pass
        if ss_url:
            st.caption(f"🔗 [開啟 Google Sheets 試算表]({ss_url})")
    else:
        # 判斷是不是在 Streamlit Cloud 上
        try:
            on_cloud = bool(st.secrets)
        except Exception:
            on_cloud = False
        if on_cloud:
            st.warning(
                "⚠️ **使用本地 CSV 儲存** — 在 Streamlit Cloud 上資料不會保存！\n\n"
                "App 重啟後會回到 GitHub repo 中的初始狀態。"
                "請參考 `SETUP_GOOGLE_SHEETS.md` 設定 Google Sheets 儲存以保留資料。"
            )
        else:
            st.info("📁 **使用本地 CSV 儲存**（localhost 開發模式）")

    st.divider()

    st.markdown("##### 📥 從 Excel / CSV 匯入")
    st.caption(
        "必要欄位：`charging_date`（或 `year`+`month`+`date` 三欄），"
        "`odometer_miles`（或 `Odometer ...`），"
        "`start_battery_pct`（或 `battery Start %`）。"
        "可選欄位：`final_battery_pct`（缺則預設 80）。"
        "電量可為 0-1 小數或 0-100 整數，會自動偵測。"
    )

    template_df = pd.DataFrame(
        {
            "charging_date": ["2024-01-15", "2024-01-22", "2024-02-03"],
            "odometer_miles": [12500, 12780, 13100],
            "start_battery_pct": [25, 30, 18],
            "final_battery_pct": [85, 90, 80],
            "source_type": ["manual", "manual", "manual"],
        }
    )
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.download_button(
            "⬇️ CSV 範本",
            template_df.to_csv(index=False).encode("utf-8"),
            file_name="tesla_charging_template.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_t2:
        import io
        buf = io.BytesIO()
        try:
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                template_df.to_excel(w, index=False, sheet_name="records")
            st.download_button(
                "⬇️ Excel 範本",
                buf.getvalue(),
                file_name="tesla_charging_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except ImportError:
            st.caption("需安裝 openpyxl 才能下載 Excel 範本。")

    uploaded_file = st.file_uploader(
        "選擇 Excel (.xlsx) 或 CSV 檔",
        type=["xlsx", "xls", "csv"],
        key="bulk_import_uploader",
    )

    import_mode = st.radio(
        "匯入模式",
        ["附加到現有資料", "清除舊資料並取代"],
        horizontal=True,
        key="import_mode_radio",
    )

    # Excel 可能有多個工作表
    if uploaded_file is not None:
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                imp_df = pd.read_csv(uploaded_file)
                sheet_used = "CSV"
            else:
                # 讀取所有工作表，讓使用者選擇
                all_sheets = pd.read_excel(uploaded_file, sheet_name=None)
                # 過濾掉空白工作表
                non_empty = {k: v for k, v in all_sheets.items() if not v.empty}
                if not non_empty:
                    # 全部為空
                    imp_df = list(all_sheets.values())[0]
                    sheet_used = list(all_sheets.keys())[0]
                elif len(non_empty) == 1:
                    sheet_used = list(non_empty.keys())[0]
                    imp_df = non_empty[sheet_used]
                else:
                    sheet_used = st.selectbox("選擇工作表", list(non_empty.keys()),
                                              key="sheet_select")
                    imp_df = non_empty[sheet_used]

            st.success(f"已載入「{sheet_used}」工作表 — {len(imp_df)} 列。")
            with st.expander("👀 預覽前 10 列"):
                st.dataframe(imp_df.head(10), use_container_width=True)
        except ImportError:
            st.error("讀取 Excel 需要 `openpyxl`。請執行：pip install openpyxl")
            imp_df = None
        except Exception as e:
            st.error(f"讀取失敗：{e}")
            imp_df = None

        if imp_df is not None and st.button("📥 匯入", use_container_width=True,
                                            type="primary"):
            mode = "replace" if import_mode == "清除舊資料並取代" else "append"
            result = store.import_dataframe(imp_df, mode=mode)
            if result["imported"]:
                st.success(
                    f"✅ 成功匯入 {result['imported']:,} 筆。"
                    f"跳過 {result['skipped']:,} 筆。"
                    f"資料庫總筆數：{result['total']:,}。"
                )
            else:
                st.error(f"❌ 無資料匯入。跳過 {result['skipped']:,} 筆。")
            if result["errors"]:
                with st.expander(f"⚠️ {len(result['errors'])} 個問題"):
                    for e in result["errors"][:50]:
                        st.write(f"- {e}")
                    if len(result["errors"]) > 50:
                        st.caption(f"...另有 {len(result['errors']) - 50} 個未顯示。")
            if result["imported"]:
                st.rerun()

    st.divider()

    # ----- 匯出 -----
    st.markdown("##### 📤 匯出")
    df_all = load_df()
    if df_all.empty:
        st.info("尚無資料可匯出。")
    else:
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.download_button(
                "⬇️ 下載 CSV",
                df_all.to_csv(index=False).encode("utf-8"),
                file_name="charging_records.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_e2:
            try:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    df_all.to_excel(w, index=False, sheet_name="records")
                st.download_button(
                    "⬇️ 下載 Excel",
                    buf.getvalue(),
                    file_name="charging_records.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except ImportError:
                st.caption("需安裝 openpyxl 才能下載 Excel。")

    st.divider()

    # ----- 瀏覽 / 刪除 -----
    st.markdown("##### 🗃️ 瀏覽與刪除")
    if df_all.empty:
        st.info("尚無紀錄。")
    else:
        view_cols = [
            "charging_date", "odometer_miles", "start_battery_pct",
            "final_battery_pct", "battery_pct_added", "miles_diff",
            "season_year_label", "source_type", "record_id",
        ]
        view_df = df_all[view_cols].sort_values("charging_date", ascending=False)
        st.dataframe(
            view_df,
            use_container_width=True,
            height=320,
            column_config={
                "charging_date":     st.column_config.DateColumn("日期", format="MM/DD/YYYY"),
                "odometer_miles":    st.column_config.NumberColumn("里程", format="%,d"),
                "miles_diff":        st.column_config.NumberColumn("里程差", format="%,.1f"),
                "start_battery_pct": st.column_config.NumberColumn("起始 %", format="%d"),
                "final_battery_pct": st.column_config.NumberColumn("結束 %", format="%d"),
                "battery_pct_added": st.column_config.NumberColumn("增加 %", format="%d"),
                "season_year_label": "季節",
                "source_type":       "來源",
                "record_id":         "ID",
            },
        )

        delete_id = st.text_input("用 record_id 刪除單筆", key="delete_id_input",
                                  help="從上方表格複製 ID 貼到這裡")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            if st.button("🗑️ 刪除", use_container_width=True,
                         disabled=not delete_id.strip()):
                ok = store.delete_by_id(delete_id.strip())
                if ok:
                    st.success("已刪除。")
                    st.rerun()
                else:
                    st.error("找不到該 ID。")
        with col_d2:
            with st.expander("⚠️ 危險區"):
                confirm = st.text_input("輸入 DELETE 清空所有資料",
                                        key="wipe_confirm")
                if st.button("💣 清空所有資料", use_container_width=True,
                             disabled=(confirm != "DELETE")):
                    store.clear_all()
                    st.success("已清空所有資料。")
                    st.rerun()
