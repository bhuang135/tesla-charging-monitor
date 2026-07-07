"""
ui_components.py
----------------
UI 元件：行動裝置優先 CSS、KPI 卡片、區塊標題、狀態徽章。

重要 UI 行為：
- viewport meta 標籤允許 iOS Safari / Chrome 雙指縮放
- 標題避開 Streamlit 頂部工具列遮擋
- 分頁標籤橫向捲動且不重疊
"""

from __future__ import annotations

import streamlit as st


def inject_mobile_css() -> None:
    """注入行動裝置友善的 CSS + viewport 設定。"""

    # --- 覆寫 viewport meta 讓 iOS Safari/Chrome 可雙指縮放 ---
    st.markdown(
        """
        <script>
        (function() {
          try {
            var meta = document.querySelector('meta[name="viewport"]');
            if (!meta) {
              meta = document.createElement('meta');
              meta.name = 'viewport';
              document.head.appendChild(meta);
            }
            meta.setAttribute(
              'content',
              'width=device-width, initial-scale=1.0, minimum-scale=0.5, maximum-scale=5.0, user-scalable=yes'
            );
          } catch (e) { /* no-op */ }
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /* ---- 允許縮放 ---- */
        html, body {
            touch-action: auto !important;
            -webkit-text-size-adjust: 100%;
        }

        /* ---- 全域容器 ----
           行動：窄、留白；桌面：較寬、舒適邊距
           padding-top 必須夠大才能避開 Streamlit 頂部的 toolbar
           （包含 hamburger 選單、Deploy 按鈕、Running indicator） */
        .block-container {
            padding-top: 5rem !important;
            padding-bottom: 4rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 960px !important;
        }
        @media (max-width: 640px) {
            .block-container {
                padding-top: 4.5rem !important;
                padding-left: 0.6rem !important;
                padding-right: 0.6rem !important;
                max-width: 100% !important;
            }
        }

        /* Streamlit toolbar 一律顯示在最上層 + 給內容留空間 */
        [data-testid="stHeader"] {
            background: rgba(14,17,23,0.92) !important;
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            z-index: 999990 !important;
        }
        [data-testid="stToolbar"] {
            z-index: 999991 !important;
        }
        @media (prefers-color-scheme: light) {
            [data-testid="stHeader"] {
                background: rgba(255,255,255,0.92) !important;
            }
        }

        /* ---- App 標題 ---- */
        .app-header {
            text-align: center;
            padding: 0.4rem 0 0.5rem 0;
            border-bottom: 1px solid rgba(120,120,120,0.15);
            margin-bottom: 0.6rem;
            overflow: hidden;
        }
        .app-title {
            font-size: 1.1rem;
            font-weight: 700;
            letter-spacing: -0.01em;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            line-height: 1.2;
        }
        .app-sub {
            font-size: 0.72rem;
            opacity: 0.7;
            line-height: 1.2;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        @media (min-width: 641px) {
            .app-title { font-size: 1.35rem; }
            .app-sub   { font-size: 0.85rem; }
        }

        /* ---- 區塊標題 ---- */
        .section-header {
            font-size: 1.05rem;
            font-weight: 700;
            margin: 0.4rem 0 0.6rem 0;
        }
        @media (min-width: 641px) {
            .section-header { font-size: 1.15rem; }
        }

        /* ---- KPI 卡片 ---- */
        .kpi-card {
            background: rgba(127,127,127,0.06);
            border: 1px solid rgba(127,127,127,0.15);
            border-radius: 14px;
            padding: 0.65rem 0.75rem;
            margin-bottom: 0.4rem;
            text-align: left;
            min-height: 70px;
        }
        .kpi-label {
            font-size: 0.72rem;
            opacity: 0.7;
            margin-bottom: 0.15rem;
            font-weight: 500;
        }
        .kpi-value {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.01em;
        }
        @media (min-width: 641px) {
            .kpi-label { font-size: 0.78rem; }
            .kpi-value { font-size: 1.35rem; }
        }

        /* ---- 指標卡片 ---- */
        .indicator-card {
            border-radius: 14px;
            padding: 0.7rem 0.85rem;
            margin-bottom: 0.55rem;
            border-left: 5px solid #888;
            background: rgba(127,127,127,0.05);
        }
        .indicator-card.green  { border-left-color: #2ea043; background: rgba(46,160,67,0.08); }
        .indicator-card.yellow { border-left-color: #d29922; background: rgba(210,153,34,0.10); }
        .indicator-card.red    { border-left-color: #cf222e; background: rgba(207,34,46,0.10); }

        .ind-title {
            font-weight: 700;
            font-size: 0.92rem;
            margin-bottom: 0.2rem;
        }
        .ind-detail {
            font-size: 0.84rem;
            opacity: 0.85;
        }

        /* ---- 狀態徽章 ---- */
        .badge {
            display: inline-block;
            padding: 0.05rem 0.5rem;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 700;
            margin-left: 0.35rem;
            vertical-align: middle;
        }
        .badge.green  { background: #2ea043; color: #fff; }
        .badge.yellow { background: #d29922; color: #fff; }
        .badge.red    { background: #cf222e; color: #fff; }

        /* ---- 按鈕 ---- */
        .stButton > button {
            min-height: 44px;
            border-radius: 12px;
            font-weight: 600;
        }

        /* ---- 分頁標籤 — 解決 iPhone 直拿時圖示與文字重疊問題 ---- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            flex-wrap: nowrap;
            border-bottom: 1px solid rgba(127,127,127,0.2);
        }
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {
            height: 3px;
        }
        .stTabs [data-baseweb="tab"] {
            white-space: nowrap !important;
            padding: 8px 10px !important;
            font-size: 0.85rem !important;
            line-height: 1.3 !important;
            min-width: max-content !important;
            flex-shrink: 0 !important;
        }
        /* 確保每個 tab 的內容（emoji + 文字）水平排列、不換行 */
        .stTabs [data-baseweb="tab"] p {
            white-space: nowrap !important;
            margin: 0 !important;
            line-height: 1.3 !important;
        }
        .stTabs [data-baseweb="tab"] [data-testid="stMarkdownContainer"] {
            display: inline-block !important;
        }
        @media (min-width: 641px) {
            .stTabs [data-baseweb="tab"] {
                padding: 8px 14px !important;
                font-size: 0.95rem !important;
            }
        }

        /* ---- 數字輸入：避免 iOS 自動縮放 ---- */
        input[type="text"], input[type="number"], textarea, select {
            font-size: 16px !important;
        }

        /* ---- 隱藏不需要的 Streamlit 元件 ---- */
        #MainMenu {visibility: hidden;}
        footer    {visibility: hidden;}

        /* ---- 圖表 / 表格不溢出，且鎖定 iOS 的觸控縮放 ---- */
        .stPlotlyChart, .stDataFrame {
            max-width: 100%;
            overflow-x: auto;
        }
        /* 防止在 Plotly 圖表上雙指/雙擊縮放（iPhone 滑動時不要動） */
        .stPlotlyChart, .stPlotlyChart * {
            touch-action: pan-x pan-y !important;
        }
        /* 圖表內部禁止滑動時被誤觸到「pinch zoom」事件 */
        .js-plotly-plot, .plotly, .plot-container {
            touch-action: pan-y !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_header(text: str) -> None:
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(color: str) -> str:
    """傳回行內狀態徽章（'green' / 'yellow' / 'red'）。"""
    label = {"green": "正常", "yellow": "注意", "red": "警示"}.get(color, color.upper())
    return f'<span class="badge {color}">{label}</span>'


def fmt_miles(v) -> str:
    """格式化里程數字含千分位。空值傳回 '—'。"""
    if v is None:
        return "—"
    try:
        if v != v:
            return "—"
    except Exception:
        pass
    return f"{v:,.0f}"


def fmt_pct(v, decimals: int = 1) -> str:
    if v is None:
        return "—"
    try:
        if v != v:
            return "—"
    except Exception:
        pass
    return f"{v:.{decimals}f}%"


def plotly_static_config() -> dict:
    """
    Plotly chart 設定 — 鎖定滑動時的縮放/平移。

    使用方式：
        st.plotly_chart(fig, use_container_width=True, config=plotly_static_config())

    這樣做之後：
    - iPhone 滑動圖表時不會自動縮放
    - 雙指縮放仍會作用於整個頁面（瀏覽器 pinch-zoom）而非圖表
    - 工具列只保留 reset/download，移除選取/平移/縮放
    """
    return {
        "displayModeBar": False,        # 行動裝置隱藏工具列
        "scrollZoom": False,            # 不允許捲動縮放
        "doubleClick": "reset",         # 雙擊只是重設
        "displaylogo": False,
        "responsive": True,
        "staticPlot": False,            # 仍然可 hover，只是禁止縮放
        "modeBarButtonsToRemove": [
            "zoom2d", "pan2d", "select2d", "lasso2d",
            "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
        ],
    }
