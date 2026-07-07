"""
ocr_extractor.py
----------------
使用 Google Gemini Vision 進行 OCR 擷取。

採用 2025 GA 版的 google-genai SDK（舊版 google-generativeai 已於 2025/11/30 停止維護）。

需求：
    pip install google-genai pillow
    GEMINI_API_KEY 透過下列任一方式提供：
      - Streamlit secrets (.streamlit/secrets.toml)
      - 環境變數 GEMINI_API_KEY 或 GOOGLE_API_KEY
      - 在 App 介面中輸入

Public API:
    extract_from_image(image_path, custom_prompt=None) -> dict
"""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Dict, Any, Optional


OCR_BACKENDS = ["gemini", "manual"]

DEFAULT_PROMPT = (
    "你會看到一張 Tesla 儀表板或充電畫面照片。請辨識其中兩個數值：\n"
    "1. odometer_miles：里程數（以 miles 為單位的整數，通常是 4-6 位數，可能在右下或顯示器中央）\n"
    "2. start_battery_pct：當前電池電量百分比（0-100 的整數，通常在電量條附近、有 % 符號）\n\n"
    "請僅以下列嚴格 JSON 格式回覆，不要包含任何其他文字、解釋或 markdown：\n"
    '{"odometer_miles": <整數或 null>, '
    '"start_battery_pct": <0-100整數或 null>, '
    '"confidence": <0-1 之間的浮點數>, '
    '"notes": "<簡短說明你看到什麼>"}\n\n'
    "若無法辨識某個值，請填 null。confidence 反映你的辨識信心。"
)


def _empty_result(note: str = "無法讀取影像，請手動輸入數值。") -> Dict[str, Any]:
    return {
        "odometer_miles": None,
        "start_battery_pct": None,
        "confidence": 0.0,
        "notes": note,
    }


def _get_secret(name: str) -> Optional[str]:
    """從 Streamlit secrets 或環境變數讀取金鑰。"""
    # 先試 Streamlit secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets") and name in st.secrets:
            val = st.secrets[name]
            if val:
                return str(val)
    except Exception:
        pass
    # 再試環境變數
    return os.environ.get(name)


def _get_api_key(override: Optional[str] = None) -> Optional[str]:
    """取得 Gemini API key（優先使用呼叫者提供的，再從 secrets/env 找）。"""
    if override:
        return override
    return _get_secret("GEMINI_API_KEY") or _get_secret("GOOGLE_API_KEY")


def _parse_json_response(text: str) -> Dict[str, Any]:
    """解析模型回傳的 JSON 字串（容錯處理 code fence）。"""
    text = text.strip()
    # 移除 markdown 程式碼框
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    # 找到第一個 { 到最後一個 }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def _extract_gemini(image_path: str,
                    custom_prompt: Optional[str] = None,
                    api_key: Optional[str] = None,
                    model_name: str = "gemini-2.5-flash") -> Dict[str, Any]:
    """使用新版 google-genai SDK 呼叫 Gemini Vision。"""
    key = _get_api_key(api_key)
    if not key:
        return _empty_result(
            "未設定 Gemini API Key。請在「新增」分頁中輸入，"
            "或於 .streamlit/secrets.toml 中設定 GEMINI_API_KEY。"
        )

    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError:
        return _empty_result(
            "未安裝 google-genai。請執行：pip install google-genai"
        )

    if not os.path.exists(image_path):
        return _empty_result(f"找不到影像檔：{image_path}")

    try:
        # 讀取影像為 bytes
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # 推斷 mime type
        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "png": "image/png", "webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/jpeg")

        client = genai.Client(api_key=key)
        prompt = custom_prompt or DEFAULT_PROMPT

        response = client.models.generate_content(
            model=model_name,
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )

        raw = response.text or ""
        if not raw.strip():
            return _empty_result("Gemini 回覆為空。")

        data = _parse_json_response(raw)
        odo = data.get("odometer_miles")
        sb = data.get("start_battery_pct")
        return {
            "odometer_miles": int(odo) if odo is not None else None,
            "start_battery_pct": int(sb) if sb is not None else None,
            "confidence": float(data.get("confidence", 0.0) or 0.0),
            "notes": str(data.get("notes", ""))[:300],
        }
    except Exception as e:
        # 不洩漏 API key
        msg = str(e).replace(key, "***") if key else str(e)
        return _empty_result(f"Gemini 呼叫失敗：{msg[:200]}")


def extract_from_image(image_path: str,
                       backend: str = "gemini",
                       custom_prompt: Optional[str] = None,
                       api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    從影像擷取里程與電量百分比。

    參數：
        image_path     影像檔路徑
        backend        'gemini' 或 'manual'
        custom_prompt  覆寫預設 prompt
        api_key        覆寫從 secrets/env 讀到的 API key

    傳回：
        dict — odometer_miles, start_battery_pct, confidence, notes
    """
    if backend == "manual":
        return _empty_result("手動模式 — 請在下方輸入數值。")
    return _extract_gemini(image_path, custom_prompt=custom_prompt, api_key=api_key)


def has_api_key() -> bool:
    """檢查環境中是否已設定 Gemini API key（不檢查使用者即時輸入）。"""
    return bool(_get_secret("GEMINI_API_KEY") or _get_secret("GOOGLE_API_KEY"))
