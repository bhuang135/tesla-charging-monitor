"""
analytics.py
------------
KPI computation, aggregations, and Plotly chart factories.

All charts use Plotly for interactive, mobile-friendly rendering.
"""

from __future__ import annotations

from typing import Dict, Any, List

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# -------------------------------------------------------------------
# Defaults / constants
# -------------------------------------------------------------------
LOW_BATTERY_THRESHOLD_DEFAULT = 20  # % — start_battery_pct below this counts as "low"

WEEKDAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

SEASON_ORDER = ["Spring", "Summer", "Fall", "Winter"]


# -------------------------------------------------------------------
# KPIs
# -------------------------------------------------------------------
def overview_kpis(df: pd.DataFrame,
                  low_battery_threshold: int = LOW_BATTERY_THRESHOLD_DEFAULT) -> Dict[str, Any]:
    """Compute the overview dashboard KPIs."""
    total = len(df)
    miles = df["miles_diff"].dropna()
    start_b = df["start_battery_pct"].dropna()
    final_b = df["final_battery_pct"].dropna()
    added = df["battery_pct_added"].dropna()

    low_mask = df["start_battery_pct"] < low_battery_threshold
    low_count = int(low_mask.sum())

    return {
        "total_records": total,
        "avg_miles_diff": float(miles.mean()) if len(miles) else 0.0,
        "median_miles_diff": float(miles.median()) if len(miles) else 0.0,
        "max_miles_diff": float(miles.max()) if len(miles) else 0.0,
        "avg_start_battery_pct": float(start_b.mean()) if len(start_b) else 0.0,
        "avg_final_battery_pct": float(final_b.mean()) if len(final_b) else 0.0,
        "avg_battery_pct_added": float(added.mean()) if len(added) else 0.0,
        "min_start_battery_pct": float(start_b.min()) if len(start_b) else 0.0,
        "low_battery_count": low_count,
        "low_battery_rate": (low_count / total) if total else 0.0,
    }


# -------------------------------------------------------------------
# Helper: low_battery_rate per group
# -------------------------------------------------------------------
def _low_battery_rate(s: pd.Series, threshold: int = LOW_BATTERY_THRESHOLD_DEFAULT) -> float:
    if len(s) == 0:
        return 0.0
    return float((s < threshold).mean())


# -------------------------------------------------------------------
# Aggregation engine
# -------------------------------------------------------------------
def aggregate(df: pd.DataFrame, group_col: str,
              low_battery_threshold: int = LOW_BATTERY_THRESHOLD_DEFAULT) -> pd.DataFrame:
    """
    Group `df` by `group_col` and produce one row per group with the
    standard metrics.
    """
    if df.empty or group_col not in df.columns:
        return pd.DataFrame()

    g = df.groupby(group_col, dropna=False)
    out = pd.DataFrame({
        "charging_count": g.size(),
        "avg_miles_diff": g["miles_diff"].mean(),
        "avg_start_battery_pct": g["start_battery_pct"].mean(),
        "avg_final_battery_pct": g["final_battery_pct"].mean(),
        "avg_battery_pct_added": g["battery_pct_added"].mean(),
        "low_battery_rate": g["start_battery_pct"].apply(
            lambda s: _low_battery_rate(s, low_battery_threshold)
        ),
    }).reset_index()

    # Stable sort
    if group_col == "weekday":
        out["__order"] = out["weekday"].map({d: i for i, d in enumerate(WEEKDAY_ORDER)})
        out = out.sort_values("__order").drop(columns="__order")
    elif group_col == "season":
        out["__order"] = out["season"].map({s: i for i, s in enumerate(SEASON_ORDER)})
        out = out.sort_values("__order").drop(columns="__order")
    else:
        out = out.sort_values(group_col)

    return out.reset_index(drop=True)


def chart_aggregate(agg: pd.DataFrame, group_col: str, metric_key: str,
                    x_label: str, metric_label: str) -> go.Figure:
    """通用長條圖。"""
    if agg.empty:
        return _empty_chart("無資料")
    fig = px.bar(
        agg, x=group_col, y=metric_key,
        labels={group_col: x_label, metric_key: metric_label},
        title=f"{metric_label}（依{x_label}）",
    )
    _apply_mobile_layout(
        fig,
        x_axis_kind=_x_axis_kind_for_group(group_col),
        y_axis_kind=_y_axis_kind_for_metric(metric_key),
    )
    return fig


# -------------------------------------------------------------------
# "Same period across years" helpers
# -------------------------------------------------------------------
def same_period_across_years(df: pd.DataFrame, period_col: str, period_value) -> pd.DataFrame:
    """
    Filter df to records matching `period_value` in `period_col`
    (e.g. month=12, season='Winter'), then aggregate by year.

    For season='Winter', uses season_year so winter-spanning records
    are grouped correctly.
    """
    if df.empty or period_col not in df.columns:
        return pd.DataFrame()

    sub = df[df[period_col] == period_value]
    if sub.empty:
        return pd.DataFrame()

    year_col = "season_year" if period_col == "season" else "year"
    return aggregate(sub, year_col).rename(columns={year_col: "year"})


def chart_same_period_across_years(cmp_df: pd.DataFrame, metric_key: str,
                                   title: str) -> go.Figure:
    if cmp_df.empty:
        return _empty_chart("無資料")
    fig = px.bar(
        cmp_df, x="year", y=metric_key,
        title=title,
        labels={"year": "年份", metric_key: metric_key},
    )
    _apply_mobile_layout(fig, x_axis_kind="year",
                        y_axis_kind=_y_axis_kind_for_metric(metric_key))
    return fig


# -------------------------------------------------------------------
# Overview charts (page 2)
# -------------------------------------------------------------------
def chart_count_by_year(df: pd.DataFrame) -> go.Figure:
    agg = aggregate(df, "year")
    if agg.empty:
        return _empty_chart("無資料")
    fig = px.bar(agg, x="year", y="charging_count",
                 title="每年充電次數",
                 labels={"year": "年份", "charging_count": "充電次數"})
    _apply_mobile_layout(fig, x_axis_kind="year", y_axis_kind="count")
    return fig


def chart_avg_miles_diff_by_year(df: pd.DataFrame) -> go.Figure:
    agg = aggregate(df, "year")
    if agg.empty:
        return _empty_chart("無資料")
    fig = px.bar(agg, x="year", y="avg_miles_diff",
                 title="每年充電間隔平均里程",
                 labels={"year": "年份", "avg_miles_diff": "平均里程"})
    _apply_mobile_layout(fig, x_axis_kind="year", y_axis_kind="miles")
    return fig


def chart_avg_start_battery_by_year(df: pd.DataFrame) -> go.Figure:
    agg = aggregate(df, "year")
    if agg.empty:
        return _empty_chart("無資料")
    fig = px.bar(agg, x="year", y="avg_start_battery_pct",
                 title="每年平均起始電量 %",
                 labels={"year": "年份", "avg_start_battery_pct": "起始電量 %"})
    _apply_mobile_layout(fig, x_axis_kind="year", y_axis_kind="percent")
    return fig


def chart_avg_final_battery_by_year(df: pd.DataFrame) -> go.Figure:
    agg = aggregate(df, "year")
    if agg.empty:
        return _empty_chart("無資料")
    fig = px.bar(agg, x="year", y="avg_final_battery_pct",
                 title="每年平均結束電量 %",
                 labels={"year": "年份", "avg_final_battery_pct": "結束電量 %"})
    _apply_mobile_layout(fig, x_axis_kind="year", y_axis_kind="percent")
    return fig


def chart_battery_added_over_time(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("無資料")
    fig = px.scatter(
        df.sort_values("charging_date"),
        x="charging_date", y="battery_pct_added",
        trendline="lowess" if len(df) >= 5 else None,
        title="充電增加電量 % — 時間趨勢",
        labels={"charging_date": "日期", "battery_pct_added": "增加電量 %"},
    )
    _apply_mobile_layout(fig, x_axis_kind="date", y_axis_kind="percent")
    return fig


def chart_odometer_trend(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("無資料")
    fig = px.line(
        df.sort_values("charging_date"),
        x="charging_date", y="odometer_miles", markers=True,
        title="里程趨勢",
        labels={"charging_date": "日期", "odometer_miles": "里程 (miles)"},
    )
    _apply_mobile_layout(fig, x_axis_kind="date", y_axis_kind="miles")
    return fig


def chart_monthly_frequency(df: pd.DataFrame) -> go.Figure:
    """每月充電頻率長條圖。"""
    if df.empty:
        return _empty_chart("無資料")
    agg = aggregate(df, "year_month")
    fig = px.bar(agg, x="year_month", y="charging_count",
                 title="每月充電頻率",
                 labels={"year_month": "月份", "charging_count": "充電次數"})
    _apply_mobile_layout(fig, y_axis_kind="count")
    return fig


# -------------------------------------------------------------------
# Layout helpers
# -------------------------------------------------------------------
def _apply_mobile_layout(fig: go.Figure,
                        x_axis_kind: str = "auto",
                        y_axis_kind: str = "auto") -> None:
    """
    Apply mobile-friendly layout + number formatting.

    Axis kinds:
        "year"    -> integer tick format, no thousands separator (2024, 2025...)
        "miles"   -> integer with thousands separator (12,500)
        "percent" -> "%.0f" (no separator, no decimals)
        "date"    -> default date axis
        "auto"    -> Plotly default
    """
    fig.update_layout(
        margin=dict(l=10, r=10, t=50, b=40),
        height=320,
        font=dict(size=12),
        title_font=dict(size=14),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        separators=".,",  # decimal=".", thousands=","
        # 鎖定圖表縮放與拖曳互動 — iPhone 滑動時不會誤觸
        dragmode=False,
        xaxis=dict(fixedrange=True),
        yaxis=dict(fixedrange=True),
    )
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)

    AXIS_FORMATS = {
        "year":    dict(tickformat="d", separatethousands=False, type="category"),
        "miles":   dict(tickformat=",d", separatethousands=True),
        "percent": dict(tickformat=".0f", separatethousands=False, ticksuffix="%"),
        "count":   dict(tickformat="d", separatethousands=False),
        "date":    {},  # plotly handles dates
        "auto":    {},
    }

    if x_axis_kind in AXIS_FORMATS:
        fig.update_xaxes(**AXIS_FORMATS[x_axis_kind])
    if y_axis_kind in AXIS_FORMATS:
        fig.update_yaxes(**AXIS_FORMATS[y_axis_kind])


def _y_axis_kind_for_metric(metric_key: str) -> str:
    """Pick the right y-axis number format based on the metric."""
    if "miles" in metric_key:
        return "miles"
    if "pct" in metric_key or "rate" in metric_key:
        return "percent"
    if "count" in metric_key:
        return "count"
    return "auto"


def _x_axis_kind_for_group(group_col: str) -> str:
    """Pick the right x-axis format based on the grouping column."""
    if group_col in ("year",):
        return "year"
    if group_col in ("charging_date",):
        return "date"
    return "auto"


def _empty_chart(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(size=14))
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig
