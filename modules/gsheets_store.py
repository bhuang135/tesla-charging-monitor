"""
gsheets_store.py
----------------
Google Sheets-backed persistent storage for Streamlit Cloud deployment.

Why this exists:
- Streamlit Community Cloud's filesystem is **ephemeral** — every reboot wipes
  out anything written locally (including data/charging_records.csv).
- For personal apps, Google Sheets is the simplest persistent backend:
  - Completely free
  - You can view/edit the spreadsheet directly
  - No new account needed (uses your Google account)

This class exposes the same interface as `DataStore`:
    - load() -> pd.DataFrame
    - append(record: dict) -> None
    - replace(df: pd.DataFrame) -> None
    - delete_by_id(record_id: str) -> bool
    - clear_all() -> None
    - import_dataframe(df, mode) -> dict

Setup (see SETUP_GOOGLE_SHEETS.md for full instructions):
1. Create a Google Sheets spreadsheet
2. Share it with a Google Cloud service account's email
3. Put the service account JSON + spreadsheet URL in .streamlit/secrets.toml
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

import pandas as pd


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


class GSheetsStore:
    """Google Sheets backend — pluggable replacement for DataStore."""

    def __init__(self, worksheet_name: str = "charging_records"):
        self.worksheet_name = worksheet_name
        self._client = None
        self._sheet = None
        self._ws = None

    # ------------------------------------------------------------------
    def _ensure_connected(self):
        """Lazy connect — only on first read/write."""
        if self._ws is not None:
            return

        try:
            import streamlit as st
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError as e:
            raise RuntimeError(
                f"Google Sheets backend requires gspread + google-auth. "
                f"Run: pip install gspread google-auth\n\n{e}"
            )

        if "gcp_service_account" not in st.secrets:
            raise RuntimeError(
                "Google Sheets credentials not found.\n\n"
                "請在 .streamlit/secrets.toml 中加入：\n"
                "[gcp_service_account]\n"
                "type = \"service_account\"\n"
                "project_id = \"...\"\n"
                "...\n\n"
                "[gsheets]\n"
                "spreadsheet_url = \"https://docs.google.com/spreadsheets/d/...\"\n"
                "請參考 SETUP_GOOGLE_SHEETS.md 取得完整設定步驟。"
            )

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]),
            scopes=scopes,
        )
        self._client = gspread.authorize(creds)

        spreadsheet_url = st.secrets.get("gsheets", {}).get("spreadsheet_url")
        if not spreadsheet_url:
            raise RuntimeError(
                "缺少 spreadsheet_url。請在 secrets.toml 加入：\n"
                "[gsheets]\n"
                "spreadsheet_url = \"https://docs.google.com/spreadsheets/d/...\""
            )

        self._sheet = self._client.open_by_url(spreadsheet_url)

        # 取得（或建立）工作表
        try:
            self._ws = self._sheet.worksheet(self.worksheet_name)
        except Exception:
            self._ws = self._sheet.add_worksheet(
                title=self.worksheet_name, rows=1000, cols=len(COLUMNS)
            )
            self._ws.update("A1", [COLUMNS], value_input_option="RAW")

        # 確認表頭存在
        header_row = self._ws.row_values(1)
        if not header_row:
            self._ws.update("A1", [COLUMNS], value_input_option="RAW")

        # 確保字串欄位都是文字格式（避免日期自動轉換）
        try:
            self._set_text_format_for_date_column()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def load(self) -> pd.DataFrame:
        """從 Google Sheets 讀取全部紀錄。"""
        try:
            self._ensure_connected()
        except Exception as e:
            import streamlit as st
            st.error(f"❌ 無法連線 Google Sheets：{e}")
            return pd.DataFrame(columns=COLUMNS)

        try:
            records = self._ws.get_all_records()
        except Exception as e:
            import streamlit as st
            st.warning(f"讀取 Google Sheets 失敗：{e}")
            return pd.DataFrame(columns=COLUMNS)

        if not records:
            return pd.DataFrame(columns=COLUMNS)

        df = pd.DataFrame(records)
        # 補齊缺少的欄位
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[COLUMNS]

        # ⚠️ 過濾掉「全空」的 row（試算表底部可能有殘留空白行）
        # 以及不小心被複製進去的 header row（charging_date 等於字面字串 "charging_date"）
        df = df[df["charging_date"].astype(str).str.strip() != ""]
        df = df[df["charging_date"].astype(str) != "charging_date"]
        df = df.reset_index(drop=True)

        # 數字欄位先轉
        for num_col in ["odometer_miles", "previous_odometer_miles", "miles_diff",
                        "start_battery_pct", "final_battery_pct", "battery_pct_added",
                        "ocr_confidence", "year", "quarter", "month", "week_number",
                        "season_year"]:
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

        # ---- 智慧日期解析 ----
        # Google Sheets 可能把日期欄存成多種格式：
        #   "2022-12-08" (理想)
        #   "Dec-8" / "12月8日" (Sheets 自動把日期 serial number 顯示成本地格式 — 缺年份！)
        #   "12/8/2022" / "8/12/2022" (locale 差異)
        #   數字 serial number (如 44903)
        # 我們的策略：
        # 1. 先嘗試標準 parse
        # 2. 對失敗的 row，用 year + month 欄位 + 解析出的 day 重建日期
        def _smart_parse_date(row):
            raw = row["charging_date"]
            if pd.isna(raw) or str(raw).strip() == "":
                return pd.NaT
            # 嘗試 1: 標準 parse
            d = pd.to_datetime(raw, errors="coerce")
            if pd.notna(d) and d.year > 1900:
                return d
            # 嘗試 2: 從 year + month + day 欄位重建
            raw_str = str(raw).strip()
            try:
                yr = row.get("year")
                mo = row.get("month")
                if pd.notna(yr) and pd.notna(mo):
                    yr = int(yr)
                    mo = int(mo)
                    # 從 raw_str 中提取日（Dec-8 → 8；12/8 → 8；08 → 8）
                    import re
                    nums = re.findall(r"\d+", raw_str)
                    if nums:
                        # 取最大的 ≤ 31 那個當 day（避開 year）
                        candidates = [int(n) for n in nums if 1 <= int(n) <= 31]
                        if candidates:
                            day = candidates[-1]  # 取最後一個（通常是 day）
                            try:
                                return pd.Timestamp(year=yr, month=mo, day=day)
                            except Exception:
                                pass
            except Exception:
                pass
            return pd.NaT

        if "charging_date" in df.columns:
            df["charging_date"] = df.apply(_smart_parse_date, axis=1)

        # 再過濾一次：日期重建失敗的（NaT）也丟掉
        df = df.dropna(subset=["charging_date"]).reset_index(drop=True)

        return df

    # ------------------------------------------------------------------
    def append(self, record: Dict[str, Any]) -> None:
        """新增一筆紀錄到 Google Sheets。"""
        self._ensure_connected()

        # 補齊必要欄位
        rec = dict(record)
        rec.setdefault("record_id", uuid.uuid4().hex[:12])
        rec.setdefault("created_at", datetime.now())

        # 用跟 replace 一致的 _to_str 邏輯
        def _to_str(v):
            if v is None:
                return ""
            if isinstance(v, str):
                return v
            try:
                if pd.isna(v):
                    return ""
            except (TypeError, ValueError):
                pass
            # Datetime / Timestamp / date → ISO 字串
            if hasattr(v, "strftime"):
                try:
                    if hasattr(v, "hour") and (v.hour or v.minute or v.second):
                        return v.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
                return v.strftime("%Y-%m-%d")
            if hasattr(v, "isoformat"):
                return v.isoformat()
            if isinstance(v, bool):
                return "True" if v else "False"
            if isinstance(v, float):
                if v.is_integer():
                    return str(int(v))
                return f"{v:.6g}"
            return str(v)

        row = [_to_str(rec.get(col)) for col in COLUMNS]
        # 🔑 用 RAW 避免 Google Sheets 自動把日期字串轉成 serial number
        self._ws.append_row(row, value_input_option="RAW")

    # ------------------------------------------------------------------
    def replace(self, df: pd.DataFrame) -> None:
        """用新的 dataframe 完全取代 Google Sheets 內容。"""
        self._ensure_connected()

        # 確保欄位順序對
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[COLUMNS].copy()

        # 補 record_id
        if "record_id" in df.columns:
            df["record_id"] = df["record_id"].fillna("").apply(
                lambda x: x if x else uuid.uuid4().hex[:12]
            )

        # 把所有值轉成字串（給 gspread）— 處理 NaN 和 datetime
        def _to_str(v):
            if v is None:
                return ""
            if isinstance(v, str):
                return v
            try:
                if pd.isna(v):
                    return ""
            except (TypeError, ValueError):
                pass
            # Datetime / Timestamp / date 都轉成 ISO 字串
            if hasattr(v, "strftime"):
                # 純日期就只用 YYYY-MM-DD
                try:
                    if hasattr(v, "hour") and (v.hour or v.minute or v.second):
                        return v.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
                return v.strftime("%Y-%m-%d")
            if hasattr(v, "isoformat"):
                return v.isoformat()
            # 布林值
            if isinstance(v, bool):
                return "True" if v else "False"
            # 浮點數：避免 437.0 變成 437
            if isinstance(v, float):
                if v.is_integer():
                    return str(int(v))
                return f"{v:.6g}"
            return str(v)

        df_str = df.copy()
        for col in df_str.columns:
            df_str[col] = df_str[col].apply(_to_str)

        # 清空原本內容
        self._ws.clear()

        # 重新寫入 header（用 RAW 避免被當成 formula）
        self._ws.update("A1", [COLUMNS], value_input_option="RAW")

        # 如果有資料，分批寫入（避免單次 request 過大導致 timeout）
        if not df_str.empty:
            rows = df_str.values.tolist()
            # gspread 對單次 update 有 cell 數量限制
            # 200 列為一批 (200 × 21 = 4200 cells)，安全範圍內
            BATCH = 200
            current_row = 2
            for i in range(0, len(rows), BATCH):
                chunk = rows[i:i + BATCH]
                end_row = current_row + len(chunk) - 1
                last_col_letter = chr(ord('A') + len(COLUMNS) - 1)
                range_str = f"A{current_row}:{last_col_letter}{end_row}"
                # 🔑 用 RAW 而非 USER_ENTERED — 避免 Google Sheets 把 "2022-12-08"
                # 自動解析成日期型別 serial number 並顯示成「Dec-8」(缺年份)
                self._ws.update(range_str, chunk, value_input_option="RAW")
                current_row = end_row + 1

        # 設定 charging_date 欄位的儲存格格式為純文字
        # 這樣即使 Google Sheets 認為它是日期，也會以 "2022-12-08" 字串顯示
        try:
            self._set_text_format_for_date_column()
        except Exception:
            pass  # 格式化失敗不影響資料寫入

    def _set_text_format_for_date_column(self):
        """把容易被 Google Sheets 誤判為日期的欄位設成純文字格式。

        包含 charging_date / year_month / year_week / created_at / record_id 等。
        即使資料是 "2022-12-08" 字串，Sheets 也不會自動轉成日期 serial number。
        """
        try:
            from gspread.utils import rowcol_to_a1
            # 需要保護的欄位（全部都用文字格式顯示）
            protect_cols = ["record_id", "charging_date", "year_month",
                            "year_week", "weekday", "season", "season_year_label",
                            "source_type", "created_at"]
            for col_name in protect_cols:
                if col_name not in COLUMNS:
                    continue
                col_idx = COLUMNS.index(col_name) + 1  # 1-based
                start_a1 = rowcol_to_a1(1, col_idx)
                end_a1 = rowcol_to_a1(10000, col_idx)
                range_str = f"{start_a1}:{end_a1}"
                try:
                    self._ws.format(range_str, {
                        "numberFormat": {"type": "TEXT"}
                    })
                except Exception:
                    pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    def delete_by_id(self, record_id: str) -> bool:
        """刪除指定 record_id 的紀錄。"""
        self._ensure_connected()
        records = self._ws.get_all_records()
        for idx, row in enumerate(records, start=2):  # 第 1 行是 header
            if str(row.get("record_id")) == str(record_id):
                self._ws.delete_rows(idx)
                return True
        return False

    # ------------------------------------------------------------------
    def clear_all(self) -> None:
        """清空所有紀錄（保留表頭）。"""
        self._ensure_connected()
        self._ws.clear()
        self._ws.update("A1", [COLUMNS])

    # ------------------------------------------------------------------
    def import_dataframe(self, df: pd.DataFrame, mode: str = "append") -> Dict[str, Any]:
        """匯入 dataframe — 與 DataStore 同介面。
        
        流程：
        1. 用 DataStore 在臨時 CSV 上做欄位辨識 + 正規化（沿用原本邏輯）
        2. 跑 recompute_features 產生衍生欄位（year_quarter / season_year_label / 等）
        3. 一次性 replace 寫回 Google Sheets
        """
        from modules.data_store import DataStore
        from modules.feature_engineering import recompute_features
        import tempfile, os

        # ---- Step 1: 用 DataStore 處理 staging ----
        with tempfile.TemporaryDirectory() as tmp:
            tmp_csv = os.path.join(tmp, "tmp.csv")
            # 載入目前 Sheets 資料作為 baseline (mode=append)
            if mode == "append":
                try:
                    cur = self.load()
                    if not cur.empty:
                        cur.to_csv(tmp_csv, index=False)
                except Exception as e:
                    import streamlit as st
                    st.warning(f"讀取現有資料失敗（將以新資料取代）：{e}")
            ds = DataStore(tmp_csv)
            result = ds.import_dataframe(df, mode=mode)
            # 把 DataStore 處理完的最終結果讀出來
            final_df = ds.load()

        # ---- Step 2: 跑 recompute_features 補齊所有衍生欄位 ----
        if not final_df.empty:
            final_df = recompute_features(final_df)

        # ---- Step 3: 寫回 Google Sheets ----
        try:
            self.replace(final_df)
        except Exception as e:
            import streamlit as st
            st.error(f"❌ 寫入 Google Sheets 失敗：{e}")
            result["errors"].append(f"Google Sheets write failed: {e}")
        return result
