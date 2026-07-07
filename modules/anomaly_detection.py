"""
anomaly_detection.py
--------------------
電池健康代理指標（proxy）分析。提供：
- 可設定的閾值
- 每項指標的健康狀態（綠/黃/紅）
- 具體的異常事件偵測
"""

from __future__ import annotations

from typing import List, Dict, Any

import numpy as np
import pandas as pd


# 預設閾值（使用者介面可即時調整）
DEFAULT_THRESHOLDS: Dict[str, Any] = {
    "miles_diff_drop_pct": 0.20,        # 與前一可比期間相比下降 20% 觸發警示
    "low_battery_rate": 0.30,           # 超過 30% 的充電是從低電量開始
    "low_battery_threshold_pct": 20,    # 低電量定義（起始 < 20%）
    "high_start_battery_pct": 60,       # 「充電太早」門檻
    "added_increase_pct": 0.20,         # 增加電量 % 上升 20%+ ...
    "miles_flat_or_drop_pct": 0.0,      # ...但里程沒有相對應增加
}


# -------------------------------------------------------------------
def _split_halves(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(df) < 4:
        return df.iloc[0:0], df.iloc[0:0]
    midpoint = len(df) // 2
    return df.iloc[:midpoint], df.iloc[midpoint:]


def _pct_change(new: float, old: float) -> float:
    if old in (0, None) or pd.isna(old):
        return 0.0
    return (new - old) / abs(old)


# -------------------------------------------------------------------
def health_proxy_summary(df: pd.DataFrame,
                         thresholds: Dict[str, Any] = None) -> Dict[str, Any]:
    """傳回各指標的狀態（綠/黃/紅）與說明。"""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    indicators: List[Dict[str, Any]] = []

    df_sorted = df.sort_values("charging_date").reset_index(drop=True)
    half_a, half_b = _split_halves(df_sorted)

    # ---------- 1. 充電頻率趨勢 ----------
    if not half_a.empty and not half_b.empty:
        days_a = max((half_a["charging_date"].max() - half_a["charging_date"].min()).days, 1)
        days_b = max((half_b["charging_date"].max() - half_b["charging_date"].min()).days, 1)
        freq_a = len(half_a) / days_a
        freq_b = len(half_b) / days_b
        change = _pct_change(freq_b, freq_a)
        if change > 0.3:
            status, detail = "red", f"充電頻率明顯上升 (+{change*100:.0f}%)。"
        elif change > 0.1:
            status, detail = "yellow", f"充電頻率略為上升 (+{change*100:.0f}%)。"
        elif change < -0.3:
            status, detail = "green", f"充電頻率下降 ({change*100:+.0f}%) — 表示需要充電的次數變少。"
        else:
            status, detail = "green", f"充電頻率穩定 ({change*100:+.0f}%)。"
        indicators.append({"title": "充電頻率趨勢", "status": status, "detail": detail})
    else:
        indicators.append({"title": "充電頻率趨勢", "status": "yellow",
                           "detail": "資料不足，需要更多充電紀錄才能判斷。"})

    # ---------- 2. 充電間隔里程趨勢 ----------
    miles_a = half_a["miles_diff"].dropna()
    miles_b = half_b["miles_diff"].dropna()
    if len(miles_a) and len(miles_b):
        change = _pct_change(miles_b.mean(), miles_a.mean())
        if change < -t["miles_diff_drop_pct"]:
            status = "red"
            detail = (f"充電間隔里程下降 {abs(change)*100:.0f}% "
                      f"(從 {miles_a.mean():,.1f} 降至 {miles_b.mean():,.1f} miles)。")
        elif change < -0.05:
            status = "yellow"
            detail = f"充電間隔里程略為下降 ({change*100:+.0f}%)。"
        else:
            status = "green"
            detail = f"充電間隔里程穩定或上升 ({change*100:+.0f}%)。"
        indicators.append({"title": "充電間隔里程趨勢", "status": status, "detail": detail})
    else:
        indicators.append({"title": "充電間隔里程趨勢", "status": "yellow",
                           "detail": "資料不足。"})

    # ---------- 3. 起始電量行為 ----------
    start_b = df_sorted["start_battery_pct"].dropna()
    if len(start_b):
        low_rate = float((start_b < t["low_battery_threshold_pct"]).mean())
        high_starts = float((start_b > t["high_start_battery_pct"]).mean())
        if low_rate > t["low_battery_rate"]:
            status, detail = "red", (
                f"{low_rate*100:.0f}% 的充電從低於 {t['low_battery_threshold_pct']}% "
                "開始 — 頻繁深度放電。"
            )
        elif high_starts > 0.5:
            status, detail = "yellow", (
                f"{high_starts*100:.0f}% 的充電從高於 {t['high_start_battery_pct']}% "
                "開始 — 比以往更早充電。"
            )
        else:
            status, detail = "green", "起始電量行為正常。"
        indicators.append({"title": "起始電量行為", "status": status, "detail": detail})

    # ---------- 4. 增加電量 % vs 里程 ----------
    if len(half_a) and len(half_b):
        added_a = half_a["battery_pct_added"].mean()
        added_b = half_b["battery_pct_added"].mean()
        miles_chg = _pct_change(half_b["miles_diff"].mean(), half_a["miles_diff"].mean())
        added_chg = _pct_change(added_b, added_a)
        if added_chg > t["added_increase_pct"] and miles_chg <= t["miles_flat_or_drop_pct"]:
            status = "red"
            detail = (f"增加電量 % 上升 (+{added_chg*100:.0f}%) "
                      f"但充電間隔里程沒同步上升 ({miles_chg*100:+.0f}%)。")
        elif added_chg > 0.1 and miles_chg < 0:
            status, detail = "yellow", (
                f"最近增加電量 % 較多 (+{added_chg*100:.0f}%)，"
                f"但里程 {miles_chg*100:+.0f}%。"
            )
        else:
            status, detail = "green", "電量增加與里程比例正常。"
        indicators.append({"title": "增加電量 % 對比里程", "status": status, "detail": detail})

    # ---------- 5. 季節調整趨勢 ----------
    if "season_year_label" in df_sorted.columns:
        by_season = df_sorted.groupby(["season", "season_year"], dropna=False)["miles_diff"].mean()
        worst_decline = None
        worst_detail = None
        for season_en, season_cn in [("Spring", "春季"), ("Summer", "夏季"),
                                       ("Fall", "秋季"), ("Winter", "冬季")]:
            if season_en not in by_season.index.get_level_values(0):
                continue
            sub = by_season.xs(season_en, level=0).dropna().sort_index()
            if len(sub) >= 2:
                change = _pct_change(sub.iloc[-1], sub.iloc[-2])
                if worst_decline is None or change < worst_decline:
                    worst_decline = change
                    worst_detail = (f"{season_cn}：{sub.index[-2]} → {sub.index[-1]} "
                                    f"里程變化 {change*100:+.0f}%")
        if worst_decline is None:
            indicators.append({"title": "季節調整趨勢", "status": "yellow",
                               "detail": "需要至少兩年的同一季資料才能比較。"})
        elif worst_decline < -t["miles_diff_drop_pct"]:
            indicators.append({"title": "季節調整趨勢", "status": "red",
                               "detail": f"偵測到顯著下降 — {worst_detail}。"})
        elif worst_decline < -0.05:
            indicators.append({"title": "季節調整趨勢", "status": "yellow",
                               "detail": f"輕微下降 — {worst_detail}。"})
        else:
            indicators.append({"title": "季節調整趨勢", "status": "green",
                               "detail": f"控制季節變數後比較穩定。{worst_detail or ''}"})

    return {"indicators": indicators}


# -------------------------------------------------------------------
def detect_anomalies(df: pd.DataFrame,
                     thresholds: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """傳回異常事件清單（空清單表示無異常）。"""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    out: List[Dict[str, Any]] = []
    if df.empty:
        return out

    df_sorted = df.sort_values("charging_date").reset_index(drop=True)
    half_a, half_b = _split_halves(df_sorted)

    # 1. miles_diff 下降超過閾值
    miles_a = half_a["miles_diff"].dropna()
    miles_b = half_b["miles_diff"].dropna()
    if len(miles_a) and len(miles_b):
        change = _pct_change(miles_b.mean(), miles_a.mean())
        if change < -t["miles_diff_drop_pct"]:
            out.append({
                "title": f"充電間隔里程下降 {abs(change)*100:.0f}%",
                "severity": "red",
                "detail": (f"前期平均 {miles_a.mean():,.1f} mi → "
                           f"近期平均 {miles_b.mean():,.1f} mi。"
                           f"閾值 = {t['miles_diff_drop_pct']*100:.0f}%。"),
            })

    # 2. 低電量充電比例過高
    start_b = df_sorted["start_battery_pct"].dropna()
    if len(start_b):
        rate = float((start_b < t["low_battery_threshold_pct"]).mean())
        if rate > t["low_battery_rate"]:
            out.append({
                "title": f"低電量充電比例過高：{rate*100:.0f}%",
                "severity": "red",
                "detail": (f"超過 {t['low_battery_rate']*100:.0f}% 的充電從 "
                           f"{t['low_battery_threshold_pct']}% 以下開始 — "
                           "頻繁深度放電可能造成電池壓力。"),
            })

    # 3. 近期深度放電習慣
    if len(half_b):
        recent_low = float((half_b["start_battery_pct"] < t["low_battery_threshold_pct"]).mean())
        if recent_low > t["low_battery_rate"] / 2:
            out.append({
                "title": f"近期深度放電習慣：{recent_low*100:.0f}%",
                "severity": "yellow",
                "detail": (f"近期有 {recent_low*100:.0f}% 的充電從 "
                           f"{t['low_battery_threshold_pct']}% 以下開始。"),
            })

    # 4. 充電變多但每次跑的里程變少
    if not half_a.empty and not half_b.empty and len(miles_a) and len(miles_b):
        days_a = max((half_a["charging_date"].max() - half_a["charging_date"].min()).days, 1)
        days_b = max((half_b["charging_date"].max() - half_b["charging_date"].min()).days, 1)
        freq_chg = _pct_change(len(half_b) / days_b, len(half_a) / days_a)
        miles_chg = _pct_change(miles_b.mean(), miles_a.mean())
        if freq_chg > 0.15 and miles_chg < -0.05:
            out.append({
                "title": "充電變頻繁但每次跑的里程變少",
                "severity": "red",
                "detail": (f"充電頻率 {freq_chg*100:+.0f}%，"
                           f"每次里程 {miles_chg*100:+.0f}%。"),
            })

    # 5. 增加電量 % 上升但里程沒上升
    if not half_a.empty and not half_b.empty:
        added_chg = _pct_change(half_b["battery_pct_added"].mean(),
                                half_a["battery_pct_added"].mean())
        if len(miles_a) and len(miles_b):
            miles_chg = _pct_change(miles_b.mean(), miles_a.mean())
            if added_chg > t["added_increase_pct"] and miles_chg <= t["miles_flat_or_drop_pct"]:
                out.append({
                    "title": "每次充電增加的電量增加但跑不了更多里程",
                    "severity": "red",
                    "detail": (f"增加電量 % {added_chg*100:+.0f}%，"
                               f"里程 {miles_chg*100:+.0f}%。"
                               "可能反映效率下降。"),
                })

    return out
