"""
report_generator.py
-------------------
報告產生器 — 根據其他四個分頁（總覽 / 比較 / 控制 / 健康）的篩選結果
產生綜合報告。

設計理念：
- 報告不再有自己的篩選 UI
- 直接讀取使用者在「比較」「控制」「健康」分頁所做的選擇（session_state）
- 報告會把這些分頁的「資料 + 圖表 + 解讀」整合成一份可下載的分析報告

主要對外函式：
- collect_filter_state() -> dict
    從 session_state 收集所有相關篩選的當前值
- render_report_in_app(df, filter_state) -> str
    在 App 內渲染含 Plotly 圖表的報告，並回傳 Markdown 字串（供下載）
"""

from __future__ import annotations

# 版本標記 — 變更檔案時更新，便於確認 Streamlit Cloud 已部署到新版
__version__ = "2026-05-20.v3"

from typing import Dict, Any, Optional

import pandas as pd
import streamlit as st
from translations import translate_text

from modules.analytics import (
    overview_kpis,
    aggregate,
    same_period_across_years,
    LOW_BATTERY_THRESHOLD_DEFAULT,
    chart_count_by_year,
    chart_avg_miles_diff_by_year,
    chart_avg_start_battery_by_year,
    chart_avg_final_battery_by_year,
    chart_battery_added_over_time,
    chart_odometer_trend,
    chart_monthly_frequency,
    chart_aggregate,
    chart_same_period_across_years,
)
from modules.anomaly_detection import detect_anomalies, health_proxy_summary, DEFAULT_THRESHOLDS
from modules.ui_components import plotly_static_config


SEASON_EN_TO_CN = {"Spring": "春季", "Summer": "夏季", "Fall": "秋季", "Winter": "冬季"}
SEASON_CN_TO_EN = {v: k for k, v in SEASON_EN_TO_CN.items()}


# ===================================================================
# 從 session_state 收集篩選設定
# ===================================================================
def collect_filter_state() -> Dict[str, Any]:
    """從 session_state 讀取四個分頁的當前篩選值。"""
    ss = st.session_state
    return {
        # 比較分頁
        "compare_module": ss.get("cmp_select"),          # 例如 "依年份"、"同季節跨年比較" 等
        # 控制分頁
        "controlled_mode": ss.get("controlled_mode"),    # "同一季節跨年比較" 等
        "controlled_season": ss.get("cs_season"),        # "春季" "夏季" 等
        "controlled_month": ss.get("cm_month"),          # 1-12
        "controlled_quarter": ss.get("cq_q"),            # 1-4
        # 健康分頁的閾值（如果使用者調整過）
        "threshold_miles_drop": ss.get("rpt_t_miles_drop", DEFAULT_THRESHOLDS["miles_diff_drop_pct"]),
        "threshold_low_rate": ss.get("rpt_t_low_rate", DEFAULT_THRESHOLDS["low_battery_rate"]),
        "threshold_low_pct": ss.get("rpt_t_low_pct", DEFAULT_THRESHOLDS["low_battery_threshold_pct"]),
    }


def _trend_word(series: pd.Series) -> tuple[str, float]:
    s = series.dropna()
    if len(s) < 2:
        return "資料不足", 0.0
    first, last = float(s.iloc[0]), float(s.iloc[-1])
    if first == 0:
        return "持平", 0.0
    pct = (last - first) / abs(first) * 100
    if pct > 10: return "明顯上升", pct
    if pct > 2:  return "略為上升", pct
    if pct < -10: return "明顯下降", pct
    if pct < -2:  return "略為下降", pct
    return "持平", pct


def _is_meaningful(agg: pd.DataFrame, min_rows: int = 2) -> bool:
    return not agg.empty and len(agg) >= min_rows


# ===================================================================
# 主入口
# ===================================================================
def render_report_in_app(df: pd.DataFrame,
                         filter_state: Optional[Dict[str, Any]] = None) -> str:
    """
    根據 filter_state（從四個分頁繼承的篩選）產生並在 App 內渲染報告。
    回傳對應的 Markdown 字串供下載。
    """
    if df.empty:
        st.warning("尚無紀錄，無法產生報告。")
        return translate_text("# Tesla 充電報告\n\n_尚無紀錄。_")

    fs = filter_state or {}
    thresholds = {
        "miles_diff_drop_pct": fs.get("threshold_miles_drop", DEFAULT_THRESHOLDS["miles_diff_drop_pct"]),
        "low_battery_rate": fs.get("threshold_low_rate", DEFAULT_THRESHOLDS["low_battery_rate"]),
        "low_battery_threshold_pct": fs.get("threshold_low_pct", DEFAULT_THRESHOLDS["low_battery_threshold_pct"]),
    }

    md: list[str] = []
    chart_counter = {"n": 0}

    def _chart(fig, prefix: str):
        chart_counter["n"] += 1
        st.plotly_chart(
            fig,
            use_container_width=True,
            config=plotly_static_config(),
            key=f"rpt_{prefix}_{chart_counter['n']}",
        )

    # ----------------- 標頭 -----------------
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    st.markdown("# 🔋 Tesla 充電健康分析報告")
    st.caption(f"產生日期：**{today}**　・　資料筆數：**{len(df):,}**")
    md.append(f"# 🔋 Tesla 充電健康分析報告\n\n"
              f"- 產生日期：**{today}**\n"
              f"- 資料筆數：**{len(df):,}**\n")

    # 顯示「使用了哪些分頁的篩選」
    active_filters = []
    if fs.get("compare_module"):
        active_filters.append(f"比較分頁模式：**{fs['compare_module']}**")
    if fs.get("controlled_mode"):
        ctrl = fs["controlled_mode"]
        if fs.get("controlled_season") and "季節" in ctrl:
            ctrl += f"（{fs['controlled_season']}）"
        elif fs.get("controlled_month") and "月份" in ctrl:
            ctrl += f"（{fs['controlled_month']:02d} 月）"
        elif fs.get("controlled_quarter") and "季" in ctrl and "季節" not in ctrl:
            ctrl += f"（Q{fs['controlled_quarter']}）"
        active_filters.append(f"控制分頁：**{ctrl}**")
    if active_filters:
        st.caption("· 繼承自其他分頁：" + "　・　".join(active_filters))
        md.append("\n**繼承自其他分頁的篩選**：\n" + "\n".join(f"- {a}" for a in active_filters) + "\n")

    # ===================================================================
    # SECTION 1 — ❤️ 健康分析（最重要、放最前面）
    # ===================================================================
    st.markdown("---")
    st.markdown("## ❤️ 電池健康程度分析（結論優先）")
    st.caption("⚠️ 本分析為代理（proxy）分析，不是正式 Tesla 電池診斷。")
    md.append("\n---\n\n## ❤️ 電池健康程度分析（結論優先）\n\n"
              "> ⚠️ 本分析為代理（proxy）分析，不是正式 Tesla 電池診斷。\n")

    summary = health_proxy_summary(df, thresholds=thresholds)
    anomalies = detect_anomalies(df, thresholds=thresholds)

    # 顯示使用的閾值
    st.caption(
        f"使用閾值：里程下降警示 **{thresholds['miles_diff_drop_pct']*100:.0f}%**　・　"
        f"低電量比例警示 **{thresholds['low_battery_rate']*100:.0f}%**　・　"
        f"低電量定義 **<{thresholds['low_battery_threshold_pct']}%**"
    )
    md.append(f"\n_使用閾值：里程下降警示 {thresholds['miles_diff_drop_pct']*100:.0f}%，"
              f"低電量比例警示 {thresholds['low_battery_rate']*100:.0f}%，"
              f"低電量定義 <{thresholds['low_battery_threshold_pct']}%_\n")

    st.markdown("### 五大健康指標")
    md.append("\n### 五大健康指標\n")
    for ind in summary["indicators"]:
        color = ind["status"]
        emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(color, "⚪")
        label_txt = {"green": "正常", "yellow": "注意", "red": "警示"}.get(color, "?")
        st.markdown(
            f'<div class="indicator-card {color}">'
            f'<div class="ind-title">{emoji} {ind["title"]} '
            f'<span class="badge {color}">{label_txt}</span></div>'
            f'<div class="ind-detail">{ind["detail"]}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        md.append(f"- {emoji} **{ind['title']}** ({label_txt}) — {ind['detail']}")

    st.markdown("### 異常偵測結果")
    md.append("\n### 異常偵測結果\n")
    if not anomalies:
        st.success("✅ 使用目前閾值未偵測到異常。")
        md.append("✅ 使用目前閾值未偵測到異常。")
    else:
        for a in anomalies:
            color = a["severity"]
            emoji = {"yellow": "🟡", "red": "🔴"}.get(color, "⚪")
            label_txt = {"yellow": "注意", "red": "警示"}.get(color, "?")
            st.markdown(
                f'<div class="indicator-card {color}">'
                f'<div class="ind-title">{emoji} {a["title"]} '
                f'<span class="badge {color}">{label_txt}</span></div>'
                f'<div class="ind-detail">{a["detail"]}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            md.append(f"- {emoji} **{a['title']}** — {a['detail']}")

    # 總結
    red_n = sum(1 for i in summary["indicators"] if i["status"] == "red")
    yellow_n = sum(1 for i in summary["indicators"] if i["status"] == "yellow")
    if red_n:
        concl = (f"⚠️ 共偵測到 **{red_n}** 項紅色警示與 **{yellow_n}** 項黃色注意。"
                 "建議優先處理紅色項目，並透過控制變數比較進一步確認。")
    elif yellow_n:
        concl = (f"🟡 共偵測到 **{yellow_n}** 項黃色注意，整體狀況尚可，"
                 "但有可改善空間。")
    else:
        concl = "🟢 所有指標均為正常範圍，請保持目前的充電習慣。"
    if anomalies:
        concl += f" 此外有 **{len(anomalies)}** 項異常事件。"
    st.markdown(f"**📌 健康結論**：{concl}")
    md.append(f"\n**📌 健康結論**：{concl}\n")

    # ===================================================================
    # SECTION 2 — 📊 總覽分頁內容
    # ===================================================================
    st.markdown("---")
    st.markdown("## 📊 總覽分頁內容")
    st.caption("彙整總覽分頁的關鍵指標與全資料趨勢圖。")
    md.append("\n---\n\n## 📊 總覽分頁內容\n")

    kpis = overview_kpis(df)
    st.markdown("### 關鍵指標 (KPI)")
    md.append("\n### 關鍵指標 (KPI)\n")
    kpi_rows = [
        "| 指標 | 數值 |", "|---|---|",
        f"| 總充電次數 | **{kpis['total_records']:,}** |",
        f"| 平均充電間隔里程 | **{kpis['avg_miles_diff']:,.1f}** mi |",
        f"| 間隔里程中位數 | **{kpis['median_miles_diff']:,.1f}** mi |",
        f"| 最長間隔里程 | **{kpis['max_miles_diff']:,.1f}** mi |",
        f"| 平均起始電量 | **{kpis['avg_start_battery_pct']:.1f}%** |",
        f"| 平均結束電量 | **{kpis['avg_final_battery_pct']:.1f}%** |",
        f"| 平均增加電量 | **{kpis['avg_battery_pct_added']:.1f}%** |",
        f"| 最低起始電量 | **{kpis['min_start_battery_pct']:.0f}%** |",
        f"| 低電量充電次數 | **{kpis['low_battery_count']:,}** |",
        f"| 低電量充電比例 | **{kpis['low_battery_rate']*100:.1f}%** |",
    ]
    kpi_md = "\n".join(kpi_rows)
    st.markdown(kpi_md)
    md.append(kpi_md)

    st.markdown("### 圖表分析")
    md.append("\n### 圖表分析\n")

    agg_year = aggregate(df, "year")
    if _is_meaningful(agg_year):
        # 每年充電次數
        st.markdown("#### 圖 1：每年充電次數")
        _chart(chart_count_by_year(df), "ov_count")
        trend, pct = _trend_word(agg_year["charging_count"])
        txt = (f"{int(agg_year['year'].iloc[0])} → {int(agg_year['year'].iloc[-1])} 年，"
               f"充電總次數**{trend}**（{pct:+.1f}%），平均每年 **{agg_year['charging_count'].mean():,.1f}** 次。")
        if pct > 15:
            txt += " 充電次數明顯增加 — 可能反映駕駛量增加或單次能跑的里程縮短。"
        elif pct < -15:
            txt += " 充電次數減少 — 駕駛量下降或單次可跑更遠。"
        st.markdown(f"**📖 解讀**：{txt}")
        md.append(f"\n#### 圖 1：每年充電次數\n\n**📖 解讀**：{txt}\n")

        # 每年平均間隔里程
        st.markdown("#### 圖 2：每年充電間隔平均里程")
        _chart(chart_avg_miles_diff_by_year(df), "ov_miles")
        trend, pct = _trend_word(agg_year["avg_miles_diff"])
        txt = f"反映**每次充電能跑多遠**。趨勢**{trend}**（{pct:+.1f}%）。"
        if pct < -10:
            txt += " 🔴 持續下降，若非駕駛習慣改變可能反映電池效率衰退。"
        elif pct > 10:
            txt += " 🟢 上升 — 電池效能穩定或駕駛變得節能。"
        st.markdown(f"**📖 解讀**：{txt}")
        md.append(f"\n#### 圖 2：每年充電間隔平均里程\n\n**📖 解讀**：{txt}\n")

        # 起始 / 結束電量
        st.markdown("#### 圖 3：每年平均起始電量 %")
        _chart(chart_avg_start_battery_by_year(df), "ov_start")
        avg_s = agg_year["avg_start_battery_pct"].mean()
        txt = f"每次插上充電時的電量。平均 **{avg_s:.1f}%**。"
        if avg_s < 25:
            txt += " 🟡 起始電量偏低，建議提高至 20% 以上。"
        elif avg_s > 60:
            txt += " 🟢 電量充足時就充電 — 對電池壽命友善。"
        st.markdown(f"**📖 解讀**：{txt}")
        md.append(f"\n#### 圖 3：每年平均起始電量\n\n**📖 解讀**：{txt}\n")

        st.markdown("#### 圖 4：每年平均結束電量 %")
        _chart(chart_avg_final_battery_by_year(df), "ov_final")
        avg_f = agg_year["avg_final_battery_pct"].mean()
        txt = f"充飽後的電量。平均 **{avg_f:.1f}%**。"
        if avg_f > 90:
            txt += " 🟡 經常充至 90% 以上 — Tesla 建議日常 80% 即可。"
        elif 70 <= avg_f <= 85:
            txt += " 🟢 結束電量在 Tesla 建議範圍內。"
        st.markdown(f"**📖 解讀**：{txt}")
        md.append(f"\n#### 圖 4：每年平均結束電量\n\n**📖 解讀**：{txt}\n")

    # 每月頻率
    agg_month = aggregate(df, "year_month")
    if _is_meaningful(agg_month, min_rows=3):
        st.markdown("#### 圖 5：每月充電頻率")
        _chart(chart_monthly_frequency(df), "ov_month")
        s = agg_month["charging_count"]
        peak_month = agg_month.loc[s.idxmax(), "year_month"]
        txt = f"每月平均 **{s.mean():,.1f}** 次，最高為 **{peak_month}**（{s.max():,} 次）。"
        cv = s.std() / s.mean() if s.mean() > 0 else 0
        txt += " 月度波動較大，可能與旅行/季節有關。" if cv > 0.5 else " 充電頻率相對穩定。"
        st.markdown(f"**📖 解讀**：{txt}")
        md.append(f"\n#### 圖 5：每月充電頻率\n\n**📖 解讀**：{txt}\n")

    # 里程趨勢
    st.markdown("#### 圖 6：里程趨勢")
    _chart(chart_odometer_trend(df), "ov_odo")
    odo_min, odo_max = df["odometer_miles"].min(), df["odometer_miles"].max()
    days = (df["charging_date"].max() - df["charging_date"].min()).days
    daily = (odo_max - odo_min) / days if days else 0
    usage = "輕度" if daily < 15 else ("中度" if daily < 35 else "高度")
    txt = (f"累計 **{odo_max - odo_min:,.0f} mi**，平均每日 **{daily:,.1f} mi**（{usage}使用）。"
           "曲線斜率反映駕駛強度的變化。")
    st.markdown(f"**📖 解讀**：{txt}")
    md.append(f"\n#### 圖 6：里程趨勢\n\n**📖 解讀**：{txt}\n")

    # 增加電量
    if len(df) >= 5:
        st.markdown("#### 圖 7：充電增加電量 % — 時間趨勢")
        _chart(chart_battery_added_over_time(df), "ov_added")
        avg_added = df["battery_pct_added"].mean()
        txt = (f"每次充電平均增加 **{avg_added:.1f}%**。"
               "若此數值持續上升而間隔里程沒同步增加，可能反映效率下降。")
        st.markdown(f"**📖 解讀**：{txt}")
        md.append(f"\n#### 圖 7：充電增加電量 %\n\n**📖 解讀**：{txt}\n")

    # ===================================================================
    # SECTION 3 — 🔁 比較分頁內容（根據使用者在比較分頁的選擇）
    # ===================================================================
    cmp_module = fs.get("compare_module")
    if cmp_module:
        st.markdown("---")
        st.markdown(f"## 🔁 比較分頁內容：{cmp_module}")
        st.caption(f"以下圖表來自您在「比較」分頁中選擇的模式：**{cmp_module}**。")
        md.append(f"\n---\n\n## 🔁 比較分頁內容：{cmp_module}\n")

        _render_compare_section(df, cmp_module, _chart, md)

    # ===================================================================
    # SECTION 4 — ⚖️ 控制分頁內容（根據使用者在控制分頁的選擇）
    # ===================================================================
    ctrl_mode = fs.get("controlled_mode")
    if ctrl_mode:
        st.markdown("---")
        st.markdown(f"## ⚖️ 控制分頁內容：{ctrl_mode}")
        st.caption("固定時間維度後跨年比較，降低季節偏差。")
        md.append(f"\n---\n\n## ⚖️ 控制分頁內容：{ctrl_mode}\n")

        _render_controlled_section(df, fs, _chart, md)

    # ===================================================================
    # SECTION 5 — 🛠️ 建議
    # ===================================================================
    st.markdown("---")
    st.markdown("## 🛠️ 建議行動")
    md.append("\n---\n\n## 🛠️ 建議行動\n")

    recs = []
    if kpis["low_battery_rate"] > 0.2:
        recs.append("- ⚠️ 避免低電量（<20%）才充電。Tesla 建議日常維持 20–80%。")
    if kpis["avg_start_battery_pct"] > 60:
        recs.append("- 您經常電量充足時就充電，請持續觀察每次的充電里程是否同步下降。")
    if kpis["min_start_battery_pct"] < 10:
        recs.append(f"- 🔴 最低起始電量曾達 **{kpis['min_start_battery_pct']:.0f}%** — 深度放電增加電池壓力，請避免。")
    recs += [
        "- ✅ 持續記錄**結束電量 %**，能讓代理分析更精準。",
        "- 📅 **同季節跨年比較**可控制氣候影響，建議定期執行。",
        "- 📐 未來若能加入 **kWh 充電量** 或 **預估里程**，可做真正效率分析。",
        "- 📊 持續追蹤**每 1% 電量可跑里程**是否下降。",
    ]
    if any(a["severity"] == "red" for a in anomalies):
        recs.append("- 🔧 若多個控制條件下都呈下降，建議至 **Tesla 服務中心** 檢查。")
    for r in recs:
        st.markdown(r)
    md.extend(recs)

    md.append(
        "\n---\n_由 Tesla 充電健康監測 App 自動產生。本報告為基於里程與電量行為的"
        "**代理（proxy）分析**，不是正式的 Tesla 電池診斷。_"
    )
    return translate_text("\n".join(md))


# ===================================================================
# 比較分頁內容
# ===================================================================
def _render_compare_section(df, cmp_module, _chart, md):
    """根據比較分頁的模式產生對應圖表 + 解讀。"""
    # cmp_module 是「依年份」「依月」「同季節跨年比較」等中文標籤
    # 映射回 group column
    simple_map = {
        "依年份":   ("year", "年份"),
        "依季":     ("year_quarter", "季"),
        "依月":     ("year_month", "月"),
        "依週":     ("year_week", "週"),
        "依日":     ("charging_date", "日"),
        "依季節":   ("season_year_label", "季節"),
    }

    if cmp_module in simple_map:
        group_col, axis_label = simple_map[cmp_module]
        agg = aggregate(df, group_col)
        if not _is_meaningful(agg):
            st.warning("資料不足。")
            md.append("_資料不足。_")
            return
        # 對每個主要指標各畫一張圖（避免「視覺化」變成同樣的 ASCII bar）
        for metric_key, metric_label, has_meaning in [
            ("charging_count",          "充電次數",        True),
            ("avg_miles_diff",          "平均間隔里程",    True),
            ("avg_start_battery_pct",   "平均起始電量 %",  True),
        ]:
            if len(agg) < 2:
                continue
            fig = chart_aggregate(agg, group_col, metric_key, axis_label, metric_label)
            st.markdown(f"#### {metric_label}（依{axis_label}）")
            _chart(fig, f"cmp_{group_col}_{metric_key}")
            trend, pct = _trend_word(agg[metric_key])
            txt = f"**{metric_label}** 在所選維度上的趨勢為 **{trend}**（{pct:+.1f}%）。"
            st.markdown(f"**📖 解讀**：{txt}")
            md.append(f"\n#### {metric_label}（依{axis_label}）\n\n**📖 解讀**：{txt}\n")

    elif cmp_module == "同月跨年比較" or cmp_module == "同月份跨年比較":
        # 月份 1-12 都試
        rendered = 0
        for m in range(1, 13):
            cmp_df = same_period_across_years(df, "month", m)
            if not _is_meaningful(cmp_df):
                continue
            st.markdown(f"#### {m:02d} 月跨年")
            _chart(
                chart_same_period_across_years(cmp_df, "avg_miles_diff",
                                                f"{m:02d} 月 — 平均間隔里程跨年"),
                f"cmp_m_{m}",
            )
            first, last = cmp_df.iloc[0], cmp_df.iloc[-1]
            chg = ((last["avg_miles_diff"] - first["avg_miles_diff"])
                   / abs(first["avg_miles_diff"]) * 100
                   if first["avg_miles_diff"] else 0)
            txt = f"{m:02d} 月從 {int(first['year'])} → {int(last['year'])} 年，間隔里程變化 **{chg:+.1f}%**。"
            st.markdown(f"**📖 解讀**：{txt}")
            md.append(f"\n#### {m:02d} 月跨年\n\n**📖 解讀**：{txt}\n")
            rendered += 1
            if rendered >= 4: break

    elif cmp_module == "同季節跨年比較":
        for season_en, season_cn in SEASON_EN_TO_CN.items():
            cmp_df = same_period_across_years(df, "season", season_en)
            if not _is_meaningful(cmp_df):
                continue
            st.markdown(f"#### {season_cn} 跨年")
            _chart(
                chart_same_period_across_years(cmp_df, "avg_miles_diff",
                                                f"{season_cn} — 平均間隔里程跨年"),
                f"cmp_s_{season_en}",
            )
            first, last = cmp_df.iloc[0], cmp_df.iloc[-1]
            chg = ((last["avg_miles_diff"] - first["avg_miles_diff"])
                   / abs(first["avg_miles_diff"]) * 100
                   if first["avg_miles_diff"] else 0)
            direction = "上升" if chg > 0 else "下降"
            txt = (f"{season_cn}從 {int(first['year'])} → {int(last['year'])} 年，"
                   f"間隔里程**{direction} {abs(chg):.1f}%**。")
            if chg < -15:
                txt += " 🔴 控制季節後仍顯著下降 — 留意是否持續性衰退。"
            elif chg < -5:
                txt += " 🟡 有輕微下降，可持續觀察。"
            else:
                txt += " 🟢 控制季節後表現穩定或改善。"
            st.markdown(f"**📖 解讀**：{txt}")
            md.append(f"\n#### {season_cn} 跨年\n\n**📖 解讀**：{txt}\n")

    elif cmp_module == "冬季跨年比較":
        cmp_df = same_period_across_years(df, "season", "Winter")
        if _is_meaningful(cmp_df):
            st.markdown("#### 冬季跨年")
            _chart(
                chart_same_period_across_years(cmp_df, "avg_miles_diff",
                                                "冬季 — 平均間隔里程跨年"),
                "cmp_winter",
            )
            md.append("\n#### 冬季跨年（圖表）\n")

    else:
        st.info(f"暫不支援為「{cmp_module}」自動產生報告章節。")
        md.append(f"_暫不支援「{cmp_module}」的報告章節。_")


# ===================================================================
# 控制分頁內容
# ===================================================================
def _render_controlled_section(df, fs, _chart, md):
    """根據控制分頁的模式產生對應圖表 + 解讀。"""
    ctrl_mode = fs.get("controlled_mode")

    if ctrl_mode == "同一季節跨年比較":
        season_cn = fs.get("controlled_season")
        if season_cn:
            season_en = SEASON_CN_TO_EN.get(season_cn, "Winter")
            cmp_df = same_period_across_years(df, "season", season_en)
            if _is_meaningful(cmp_df):
                st.markdown(f"#### {season_cn} — 跨年比較")
                _chart(
                    chart_same_period_across_years(cmp_df, "avg_miles_diff",
                                                    f"{season_cn} — 平均間隔里程跨年"),
                    f"ctrl_s_{season_en}",
                )
                first, last = cmp_df.iloc[0], cmp_df.iloc[-1]
                chg = ((last["avg_miles_diff"] - first["avg_miles_diff"])
                       / abs(first["avg_miles_diff"]) * 100
                       if first["avg_miles_diff"] else 0)
                txt = (f"控制 **{season_cn}** 變數後，從 {int(first['year'])} → {int(last['year'])} 年，"
                       f"平均間隔里程變化 **{chg:+.1f}%**。")
                if chg < -15:
                    txt += " 🔴 在同季節跨年下仍下降明顯 — 排除季節因素後的退化更值得注意。"
                elif chg < -5:
                    txt += " 🟡 輕微下降，可持續追蹤。"
                else:
                    txt += " 🟢 控制變數後表現穩定。"
                st.markdown(f"**📖 解讀**：{txt}")
                md.append(f"\n#### {season_cn} 跨年比較\n\n**📖 解讀**：{txt}\n")
            else:
                st.warning(f"{season_cn} 跨年資料不足。")
                md.append(f"_{season_cn} 跨年資料不足。_")

    elif ctrl_mode == "同月份跨年比較":
        m = fs.get("controlled_month") or 1
        cmp_df = same_period_across_years(df, "month", m)
        if _is_meaningful(cmp_df):
            st.markdown(f"#### {m:02d} 月跨年比較")
            _chart(
                chart_same_period_across_years(cmp_df, "avg_miles_diff",
                                                f"{m:02d} 月 — 平均間隔里程跨年"),
                f"ctrl_m_{m}",
            )
            first, last = cmp_df.iloc[0], cmp_df.iloc[-1]
            chg = ((last["avg_miles_diff"] - first["avg_miles_diff"])
                   / abs(first["avg_miles_diff"]) * 100
                   if first["avg_miles_diff"] else 0)
            txt = (f"控制 **{m:02d} 月** 後，從 {int(first['year'])} → {int(last['year'])} 年，"
                   f"間隔里程變化 **{chg:+.1f}%**。")
            st.markdown(f"**📖 解讀**：{txt}")
            md.append(f"\n#### {m:02d} 月跨年比較\n\n**📖 解讀**：{txt}\n")
        else:
            st.warning(f"{m:02d} 月跨年資料不足。")
            md.append(f"_{m:02d} 月跨年資料不足。_")

    elif ctrl_mode == "同季跨年比較":
        q = fs.get("controlled_quarter") or 1
        cmp_df = same_period_across_years(df, "quarter", q)
        if _is_meaningful(cmp_df):
            st.markdown(f"#### Q{q} 跨年比較")
            _chart(
                chart_same_period_across_years(cmp_df, "avg_miles_diff",
                                                f"Q{q} — 平均間隔里程跨年"),
                f"ctrl_q_{q}",
            )
            first, last = cmp_df.iloc[0], cmp_df.iloc[-1]
            chg = ((last["avg_miles_diff"] - first["avg_miles_diff"])
                   / abs(first["avg_miles_diff"]) * 100
                   if first["avg_miles_diff"] else 0)
            txt = (f"控制 **Q{q}** 後，從 {int(first['year'])} → {int(last['year'])} 年，"
                   f"間隔里程變化 **{chg:+.1f}%**。")
            st.markdown(f"**📖 解讀**：{txt}")
            md.append(f"\n#### Q{q} 跨年比較\n\n**📖 解讀**：{txt}\n")

    elif ctrl_mode == "氣候相近季節比較":
        mild = df[df["season"].isin(["Spring", "Fall"])]
        if not mild.empty:
            agg = aggregate(mild, "season_year_label")
            if _is_meaningful(agg):
                st.markdown("#### 春/秋（氣候相近）跨年比較")
                fig = chart_aggregate(agg, "season_year_label", "avg_miles_diff",
                                       "溫和季節", "平均間隔里程")
                _chart(fig, "ctrl_mild")
                trend, pct = _trend_word(agg["avg_miles_diff"])
                txt = f"在氣候相近的春/秋季節之間，平均間隔里程的趨勢為 **{trend}**（{pct:+.1f}%）。"
                st.markdown(f"**📖 解讀**：{txt}")
                md.append(f"\n#### 春/秋跨年比較\n\n**📖 解讀**：{txt}\n")


# ===================================================================
# 向後相容 build_report — 簡單純文字版
# ===================================================================
def build_report(df, period_type=None, period_value=None, comparison_mode=None) -> str:
    """簡化的純文字版本（不畫圖）— 給舊呼叫端用。"""
    if df.empty:
        return translate_text("# Tesla 充電報告\n\n_無資料。_")
    fs = collect_filter_state() if 'st' in globals() else {}
    summary = health_proxy_summary(df)
    kpis = overview_kpis(df)
    md = [
        f"# 🔋 Tesla 充電健康報告",
        f"\n- 紀錄筆數：**{len(df):,}**\n",
        "## ❤️ 健康指標",
    ]
    for ind in summary["indicators"]:
        emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(ind["status"], "⚪")
        md.append(f"- {emoji} {ind['title']} — {ind['detail']}")
    md.append(f"\n## 📊 KPI 摘要\n")
    md.append(f"- 平均間隔里程：{kpis['avg_miles_diff']:,.1f} mi")
    md.append(f"- 平均起始電量：{kpis['avg_start_battery_pct']:.1f}%")
    md.append(f"- 低電量比例：{kpis['low_battery_rate']*100:.1f}%")
    return translate_text("\n".join(md))
