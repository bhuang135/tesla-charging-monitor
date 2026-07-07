"""
data_store.py
-------------
Persistent storage for charging records.

Currently CSV-backed. Designed so a SQLite (or other DB) implementation
can be plugged in later by writing a class that exposes the same interface:
    - load() -> pd.DataFrame
    - append(record: dict) -> None
    - replace(df: pd.DataFrame) -> None
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Dict, Any

import pandas as pd


# Canonical column order — kept identical across CSV/SQLite upgrades.
COLUMNS = [
    "record_id",
    "charging_date",
    "year",
    "quarter",
    "month",
    "year_month",
    "week_number",
    "year_week",
    "weekday",
    "season",
    "season_year",
    "odometer_miles",
    "previous_odometer_miles",
    "miles_diff",
    "start_battery_pct",
    "final_battery_pct",
    "battery_pct_added",
    "source_type",
    "ocr_confidence",
    "manual_verified",
    "created_at",
]


class DataStore:
    """CSV-backed store. Swap with SQLiteStore later without touching app code."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        os.makedirs(os.path.dirname(self.csv_path) or ".", exist_ok=True)
        if not os.path.exists(self.csv_path):
            # Create empty CSV with full schema
            pd.DataFrame(columns=COLUMNS).to_csv(self.csv_path, index=False)

    # -------------------------------------------------------------
    def load(self) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.csv_path)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame(columns=COLUMNS)
        # Ensure all columns exist (for forward-compatible reads of old CSVs)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA
        return df[COLUMNS]

    # -------------------------------------------------------------
    def append(self, record: Dict[str, Any]) -> None:
        """
        Append a raw record. Derived fields (year/quarter/etc., miles_diff,
        battery_pct_added) are filled by feature_engineering.recompute_features
        when the data is loaded — we still write minimum stable fields here
        so the CSV is self-contained.
        """
        from modules.feature_engineering import recompute_features

        df = self.load()

        new_row = {
            "record_id": str(uuid.uuid4()),
            "charging_date": record["charging_date"],
            "odometer_miles": float(record["odometer_miles"]),
            "start_battery_pct": int(record["start_battery_pct"]),
            "final_battery_pct": int(record["final_battery_pct"]),
            "source_type": record.get("source_type", "manual"),
            "ocr_confidence": float(record.get("ocr_confidence", 0.0) or 0.0),
            "manual_verified": bool(record.get("manual_verified", False)),
            "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        # Fill rest of columns with NA so concat keeps schema
        for col in COLUMNS:
            new_row.setdefault(col, pd.NA)

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        # Recompute features on the full dataframe so derived fields are
        # consistent (handles back-dated entries automatically).
        df = recompute_features(df)

        df[COLUMNS].to_csv(self.csv_path, index=False)

    # -------------------------------------------------------------
    def replace(self, df: pd.DataFrame) -> None:
        """Overwrite all rows (used for bulk edits, imports, etc.)."""
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA
        df[COLUMNS].to_csv(self.csv_path, index=False)

    # -------------------------------------------------------------
    def import_dataframe(self, new_df: pd.DataFrame,
                         mode: str = "append",
                         default_final_battery_pct: int = 80) -> Dict[str, Any]:
        """
        Bulk-import a DataFrame (e.g. from an Excel / CSV upload).

        Smart column detection — accepts multiple formats:

        Format A (canonical):
            charging_date, odometer_miles, start_battery_pct, final_battery_pct

        Format B (year/month/day split, like the provided dataset.xlsx):
            year, month, date    -> assembled into charging_date
            Odometer ( miles ... ) or odometer_miles
            battery Start % ...  -> stored as start_battery_pct
            (final_battery_pct optional — defaults to `default_final_battery_pct`)

        Battery values may be either 0-100 (integer/percentage) or 0-1 (decimal).
        Auto-detected: if the maximum value is <= 1.0, treated as decimal and
        multiplied by 100.

        Optional columns:
            source_type, ocr_confidence, manual_verified, created_at

        Modes:
            "append"  — add new rows to existing data
            "replace" — overwrite the whole CSV

        Returns: { "imported": int, "skipped": int, "errors": [str], "total": int }
        """
        from modules.feature_engineering import recompute_features

        errors: list = []
        df_in = new_df.copy()

        # ---- 1. Normalize column names (case-insensitive matching) ----
        col_map = {c.lower().strip(): c for c in df_in.columns}

        def find_col(*candidates_substrings):
            """Find a column whose lowercase name contains any of the substrings."""
            for cand in candidates_substrings:
                cand_low = cand.lower()
                # exact match first
                if cand_low in col_map:
                    return col_map[cand_low]
            # substring fallback
            for cand in candidates_substrings:
                cand_low = cand.lower()
                for low, orig in col_map.items():
                    if cand_low in low:
                        return orig
            return None

        # ---- 2. Try to find charging_date OR assemble from year/month/day ----
        date_col = find_col("charging_date", "date_charged", "charge_date")
        year_col = find_col("year")
        month_col = find_col("month")
        day_col = find_col("day", "date")  # "date" often used for day-of-month

        if date_col is None and not (year_col and month_col and day_col):
            errors.append(
                "Missing date columns. Need either 'charging_date' OR "
                "all three of 'year', 'month', 'date' (day-of-month)."
            )

        # ---- 3. Find odometer ----
        odo_col = find_col("odometer_miles", "odometer", "miles", "mileage")
        if odo_col is None:
            errors.append("Missing odometer column. Looked for 'odometer_miles', 'odometer', 'miles'.")

        # ---- 4. Find start battery ----
        sb_col = find_col("start_battery_pct", "start_battery",
                          "battery start", "battery_start", "start %", "start_pct")
        if sb_col is None:
            errors.append("Missing start battery column. Looked for 'start_battery_pct', 'battery start %'.")

        if errors:
            return {"imported": 0, "skipped": len(df_in), "errors": errors, "total": 0}

        # ---- 5. Final battery is optional ----
        fb_col = find_col("final_battery_pct", "final_battery", "end_battery", "final %")

        # ---- 6. Detect 0-1 decimal vs 0-100 percent for battery columns ----
        def to_pct(series: pd.Series) -> pd.Series:
            s = pd.to_numeric(series, errors="coerce")
            if s.dropna().max() is not None and s.dropna().max() <= 1.0:
                return (s * 100).round()
            return s.round()

        sb_series = to_pct(df_in[sb_col])
        fb_series = to_pct(df_in[fb_col]) if fb_col else None

        # ---- 7. Month name -> number ----
        MONTH_NAMES = {
            "january": 1, "jan": 1, "february": 2, "feb": 2,
            "march": 3, "mar": 3, "april": 4, "apr": 4,
            "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
            "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
            "october": 10, "oct": 10, "november": 11, "nov": 11,
            "december": 12, "dec": 12,
        }

        def parse_month(v):
            if isinstance(v, str):
                return MONTH_NAMES.get(v.strip().lower())
            try:
                return int(v)
            except Exception:
                return None

        # ---- 8. Build rows ----
        rows = []
        skipped = 0
        for idx, row in df_in.iterrows():
            try:
                # Date assembly
                if date_col is not None:
                    d = pd.to_datetime(row[date_col], errors="coerce")
                else:
                    y = int(row[year_col])
                    m = parse_month(row[month_col])
                    if m is None:
                        skipped += 1
                        errors.append(f"Row {idx + 2}: cannot parse month '{row[month_col]}'")
                        continue
                    dd = int(row[day_col])
                    d = pd.Timestamp(year=y, month=m, day=dd)

                if pd.isna(d):
                    skipped += 1
                    errors.append(f"Row {idx + 2}: invalid date")
                    continue

                # Odometer
                odo_raw = row[odo_col]
                if pd.isna(odo_raw):
                    skipped += 1
                    errors.append(f"Row {idx + 2}: empty odometer")
                    continue
                odo = float(odo_raw)
                if odo < 0:
                    skipped += 1
                    errors.append(f"Row {idx + 2}: negative odometer ({odo})")
                    continue

                # Start battery
                sb_v = sb_series.iloc[idx]
                if pd.isna(sb_v):
                    skipped += 1
                    errors.append(f"Row {idx + 2}: empty start_battery_pct")
                    continue
                sb = int(sb_v)
                if not (0 <= sb <= 100):
                    skipped += 1
                    errors.append(f"Row {idx + 2}: start_battery_pct out of 0–100 ({sb})")
                    continue

                # Final battery
                if fb_series is not None and not pd.isna(fb_series.iloc[idx]):
                    fb = int(fb_series.iloc[idx])
                    if not (0 <= fb <= 100):
                        skipped += 1
                        errors.append(f"Row {idx + 2}: final_battery_pct out of 0–100 ({fb})")
                        continue
                else:
                    fb = int(default_final_battery_pct)

                new_row = {
                    "record_id": str(uuid.uuid4()),
                    "charging_date": d.date().isoformat(),
                    "odometer_miles": odo,
                    "start_battery_pct": sb,
                    "final_battery_pct": fb,
                    "source_type": str(row.get("source_type", "import")),
                    "ocr_confidence": float(row.get("ocr_confidence", 0.0) or 0.0),
                    "manual_verified": bool(row.get("manual_verified", True)),
                    "created_at": datetime.utcnow().isoformat(timespec="seconds"),
                }
                for col in COLUMNS:
                    new_row.setdefault(col, pd.NA)
                rows.append(new_row)
            except Exception as e:
                skipped += 1
                errors.append(f"Row {idx + 2}: {e}")

        if not rows:
            return {"imported": 0, "skipped": skipped, "errors": errors, "total": 0}

        new_part = pd.DataFrame(rows)
        if mode == "replace":
            combined = new_part
        else:
            combined = pd.concat([self.load(), new_part], ignore_index=True)

        combined = recompute_features(combined)
        combined[COLUMNS].to_csv(self.csv_path, index=False)
        return {
            "imported": len(rows),
            "skipped": skipped,
            "errors": errors,
            "total": len(combined),
        }

    # -------------------------------------------------------------
    def delete_by_id(self, record_id: str) -> bool:
        """Delete a single record by its UUID. Returns True if found."""
        df = self.load()
        before = len(df)
        df = df[df["record_id"] != record_id]
        if len(df) == before:
            return False
        self.replace(df)
        return True

    def clear_all(self) -> None:
        """Wipe all records — keeps the CSV header."""
        pd.DataFrame(columns=COLUMNS).to_csv(self.csv_path, index=False)


# ---------------------------------------------------------------
# Future SQLite implementation skeleton (TODO when needed):
#
# class SQLiteStore:
#     def __init__(self, db_path: str): ...
#     def load(self) -> pd.DataFrame: ...
#     def append(self, record: dict) -> None: ...
#     def replace(self, df: pd.DataFrame) -> None: ...
#
# Then simply swap `DataStore(CSV_PATH)` with `SQLiteStore(DB_PATH)` in app.py.
