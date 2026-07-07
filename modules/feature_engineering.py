"""
feature_engineering.py
----------------------
Derived feature computation:
- year, quarter, month, year_month, week_number, year_week, weekday
- season (Spring/Summer/Fall/Winter)
- season_year — winter 2025 = Dec 2024 + Jan 2025 + Feb 2025
- year_quarter, season_year_label (e.g. "Winter 2025")
- previous_odometer_miles, miles_diff
- battery_pct_added
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Union

import numpy as np
import pandas as pd


DateLike = Union[str, date, datetime, pd.Timestamp]


# -------------------------- Season helpers --------------------------
def season_for_date(d: DateLike) -> str:
    """Return Spring / Summer / Fall / Winter for a given date.
    Returns empty string for NaT / invalid dates."""
    d = pd.to_datetime(d, errors="coerce")
    if pd.isna(d):
        return ""
    m = d.month
    if m in (3, 4, 5):
        return "Spring"
    if m in (6, 7, 8):
        return "Summer"
    if m in (9, 10, 11):
        return "Fall"
    return "Winter"  # 12, 1, 2


def season_year_for_date(d: DateLike):
    """
    Return the *season year* for a given date.

    Winter spans the year boundary, so:
    - December 2024  -> Winter 2025
    - January  2025  -> Winter 2025
    - February 2025  -> Winter 2025

    Returns pd.NA for NaT / invalid dates (so .astype("Int64") works).
    """
    d = pd.to_datetime(d, errors="coerce")
    if pd.isna(d):
        return pd.NA
    if d.month == 12:
        return int(d.year + 1)
    return int(d.year)


# -------------------------- Main feature pipeline --------------------------
def recompute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recompute all derived fields from raw columns:
      - charging_date
      - odometer_miles
      - start_battery_pct
      - final_battery_pct
      - created_at

    Idempotent: safe to call on already-derived dataframes.
    """
    if df.empty:
        return df

    df = df.copy()

    # ----- Parse dates -----
    df["charging_date"] = pd.to_datetime(df["charging_date"], errors="coerce")
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    # ⚠️ 過濾掉無效日期的紀錄（避免後續 .dt.year 等運算炸掉）
    # 這通常發生在從 Google Sheets 讀回時，有空 row 或誤插入的 header row
    before = len(df)
    df = df.dropna(subset=["charging_date"]).reset_index(drop=True)
    if len(df) < before:
        import warnings
        warnings.warn(
            f"recompute_features: dropped {before - len(df)} rows with invalid charging_date"
        )

    if df.empty:
        return df

    # ----- Sort canonically -----
    df = df.sort_values(["charging_date", "created_at"]).reset_index(drop=True)

    # ----- Numeric coercions -----
    df["odometer_miles"] = pd.to_numeric(df["odometer_miles"], errors="coerce")
    df["start_battery_pct"] = pd.to_numeric(df["start_battery_pct"], errors="coerce")
    df["final_battery_pct"] = pd.to_numeric(df["final_battery_pct"], errors="coerce")

    # ----- Calendar features -----
    df["year"] = df["charging_date"].dt.year
    df["quarter"] = df["charging_date"].dt.quarter
    df["month"] = df["charging_date"].dt.month
    df["year_month"] = df["charging_date"].dt.strftime("%Y-%m")
    iso = df["charging_date"].dt.isocalendar()
    df["week_number"] = iso["week"].astype("Int64")
    # year_week using ISO year so weeks at year-boundaries are sensible
    df["year_week"] = (
        iso["year"].astype("Int64").astype(str) + "-W"
        + iso["week"].astype("Int64").astype(str).str.zfill(2)
    )
    df["weekday"] = df["charging_date"].dt.day_name()

    # Convenience composite
    df["year_quarter"] = df["year"].astype("Int64").astype(str) + "-Q" + df["quarter"].astype("Int64").astype(str)

    # ----- Season features -----
    df["season"] = df["charging_date"].apply(season_for_date)
    df["season_year"] = df["charging_date"].apply(season_year_for_date).astype("Int64")
    df["season_year_label"] = df["season"].astype(str) + " " + df["season_year"].astype(str)

    # ----- Diffs (mileage, battery added) -----
    df["previous_odometer_miles"] = df["odometer_miles"].shift(1)
    df["miles_diff"] = df["odometer_miles"] - df["previous_odometer_miles"]
    # First record -> miles_diff NaN per spec
    df.loc[df.index == 0, "miles_diff"] = np.nan

    df["battery_pct_added"] = df["final_battery_pct"] - df["start_battery_pct"]

    return df
