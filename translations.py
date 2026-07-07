"""
translations.py
---------------
Lightweight built-in i18n layer for the Tesla Charging Health Monitor.

Design:
- Keep the original business logic stable by returning original option values
  from Streamlit widgets.
- Translate labels, Markdown, captions, buttons, tabs, chart titles, axis titles,
  and downloaded Markdown reports at render time.
- Use deterministic local translation maps. No browser translation and no paid
  translation API is required.
"""

from __future__ import annotations

from functools import wraps
from typing import Any
import copy
import re

LANG_OPTIONS = {
    "繁體中文": "zh-TW",
    "简体中文": "zh-CN",
    "English": "en",
}

LANG_LABELS = {
    "zh-TW": "繁體中文",
    "zh-CN": "简体中文",
    "en": "English",
}

DEFAULT_LANG = "zh-TW"


def current_language() -> str:
    try:
        import streamlit as st  # type: ignore
        return st.session_state.get("app_language", DEFAULT_LANG)
    except Exception:
        return DEFAULT_LANG


def init_language_selector(st: Any) -> str:
    """Render the language selector and store the selected language in session state."""
    if "app_language" not in st.session_state:
        st.session_state["app_language"] = DEFAULT_LANG

    current = st.session_state.get("app_language", DEFAULT_LANG)
    labels = list(LANG_OPTIONS.keys())
    default_label = LANG_LABELS.get(current, "繁體中文")

    try:
        with st.sidebar:
            st.markdown("### 🌐 Language / 語言")
            selected_label = st.selectbox(
                "Choose app language",
                labels,
                index=labels.index(default_label) if default_label in labels else 0,
                key="language_selector_display",
            )
        st.session_state["app_language"] = LANG_OPTIONS[selected_label]
    except Exception:
        # In rare cases Streamlit may not allow sidebar rendering yet.
        pass

    return st.session_state.get("app_language", DEFAULT_LANG)


# ---------------------------------------------------------------------
# Traditional -> Simplified conversion
# ---------------------------------------------------------------------
# This is a compact deterministic map covering the app's UI/report terms.
# It is intentionally dependency-free for Streamlit Cloud deployment.
_ZH_CN_PHRASES = {
    "繁體中文": "繁體中文",
    "簡體中文": "简体中文",
    "充電": "充电",
    "電池": "电池",
    "電量": "电量",
    "健康監測": "健康监测",
    "監測": "监测",
    "總覽": "总览",
    "資料": "资料",
    "紀錄": "记录",
    "報告": "报告",
    "時區": "时区",
    "今日": "今天",
    "新增": "新增",
    "比較": "比较",
    "控制變數": "控制变量",
    "變數": "变量",
    "跨年": "跨年",
    "季節": "季节",
    "同月份": "同月份",
    "同一季節": "同一季节",
    "氣候": "气候",
    "開冷氣": "开冷气",
    "開暖氣": "开暖气",
    "預熱": "预热",
    "影響": "影响",
    "降低": "降低",
    "偏差": "偏差",
    "偵測": "侦测",
    "辨識": "识别",
    "擷取": "提取",
    "輸入": "输入",
    "選擇": "选择",
    "儲存": "储存",
    "匯入": "导入",
    "匯出": "导出",
    "下載": "下载",
    "刪除": "删除",
    "清空": "清空",
    "試算表": "电子表格",
    "工作表": "工作表",
    "無資料": "无资料",
    "無紀錄": "无记录",
    "無法": "无法",
    "請": "请",
    "確認": "确认",
    "錯誤": "错误",
    "警示": "警示",
    "注意": "注意",
    "正常": "正常",
    "結束": "结束",
    "起始": "起始",
    "增加": "增加",
    "平均": "平均",
    "間隔": "间隔",
    "里程": "里程",
    "月份": "月份",
    "年份": "年份",
    "週數": "周数",
    "星期": "星期",
    "綜合": "综合",
    "產生": "生成",
    "代理": "代理",
    "正式": "正式",
    "診斷": "诊断",
    "趨勢": "趋势",
    "圖表": "图表",
    "解讀": "解读",
    "建議": "建议",
    "行動": "行动",
    "瀏覽": "浏览",
    "暫存": "暂存",
    "照片": "照片",
    "拍照": "拍照",
    "上傳": "上传",
    "手動": "手动",
    "開啟": "开启",
    "載入": "加载",
    "成功": "成功",
    "失敗": "失败",
    "範本": "模板",
    "欄位": "字段",
    "數值": "数值",
    "筆": "笔",
    "列": "列",
    "顯示": "显示",
    "尚無": "暂无",
    "舊資料": "旧资料",
    "現有資料": "现有资料",
    "持久化": "持久化",
    "本地": "本地",
    "檔案": "文件",
    "環境": "环境",
    "金鑰": "密钥",
    "設定": "设置",
    "閾值": "阈值",
    "危險區": "危险区",
    "找不到": "找不到",
    "問題": "问题",
    "另有": "另有",
    "未顯示": "未显示",
    "已刪除": "已删除",
    "已清空所有資料": "已清空所有资料",
    "低電量": "低电量",
    "深度放電": "深度放电",
    "電池壓力": "电池压力",
    "電池壽命": "电池寿命",
    "結論": "结论",
    "優先": "优先",
    "採用": "采用",
    "定義": "定义",
    "充飽後": "充满后",
    "效率衰退": "效率衰退",
    "持續": "持续",
    "觀察": "观察",
    "資料筆數": "资料笔数",
    "筆數": "笔数",
}

_ZH_CN_CHARS = str.maketrans({
    "電": "电", "車": "车", "監": "监", "測": "测", "體": "体", "門": "门",
    "頁": "页", "總": "总", "覽": "览", "資": "资", "料": "料", "紀": "纪",
    "錄": "录", "報": "报", "時": "时", "區": "区", "間": "间", "週": "周",
    "歲": "岁", "數": "数", "據": "据", "圖": "图", "標": "标", "題": "题",
    "選": "选", "擇": "择", "輸": "输", "入": "入", "請": "请", "確": "确",
    "認": "认", "儲": "储", "存": "存", "匯": "汇", "導": "导", "瀏": "浏",
    "覽": "览", "刪": "删", "除": "除", "啟": "启", "開": "开", "關": "关",
    "閉": "闭", "狀": "状", "態": "态", "檢": "检", "查": "查", "雲": "云",
    "產": "产", "生": "生", "趨": "趋", "勢": "势", "應": "应", "該": "该",
    "無": "无", "這": "这", "個": "个", "與": "与", "為": "为", "後": "后",
    "會": "会", "啟": "启", "動": "动", "過": "过", "濾": "滤", "條": "条",
    "篩": "筛", "種": "种", "將": "将", "來": "来", "從": "从", "當": "当",
    "顯": "显", "示": "示", "處": "处", "理": "理", "連": "连", "線": "线",
    "雙": "双", "較": "较", "異": "异", "偵": "侦", "擷": "撷", "識": "识",
    "覺": "觉", "習": "习", "慣": "惯", "輕": "轻", "穩": "稳", "讓": "让",
    "維": "维", "護": "护", "臨": "临", "舊": "旧", "壓": "压", "縮": "缩",
    "與": "与", "優": "优", "術": "术", "義": "义", "劃": "划", "項": "项",
    "萬": "万", "準": "准", "錯": "错", "誤": "误", "讀": "读", "寫": "写",
    "試": "试", "緩": "缓", "雜": "杂", "權": "权", "認": "认", "證": "证",
    "顏": "颜", "色": "色", "離": "离", "終": "终", "經": "经", "常": "常",
    "壽": "寿", "親": "亲", "節": "节", "蘋": "苹", "機": "机",
})


# ---------------------------------------------------------------------
# English translation maps
# ---------------------------------------------------------------------
# Exact UI strings. Phrase replacements below handle dynamic Markdown.
_EN_EXACT = {
    "Tesla 充電健康監測": "Tesla Charging Health Monitor",
    "電池健康代理分析": "Battery Health Proxy Analysis",
    "📷 新增": "📷 Add",
    "📊 總覽": "📊 Overview",
    "🔁 比較": "🔁 Compare",
    "⚖️ 控制": "⚖️ Control",
    "❤️ 健康": "❤️ Health",
    "📝 報告": "📝 Report",
    "🗂️ 資料": "🗂️ Data",
    "新增充電紀錄": "Add Charging Record",
    "總覽儀表板": "Overview Dashboard",
    "時段比較": "Period Comparison",
    "控制變數比較": "Controlled Comparison",
    "電池健康代理分析": "Battery Health Proxy Analysis",
    "綜合分析報告": "Integrated Analysis Report",
    "資料管理": "Data Management",
    "輸入方式": "Input Method",
    "📷 拍照 / 上傳 (Gemini Vision)": "📷 Camera / Upload (Gemini Vision)",
    "✏️ 手動輸入": "✏️ Manual Entry",
    "充電日期": "Charging Date",
    "結束時電量 %": "Ending Battery %",
    "Gemini API Key": "Gemini API Key",
    "##### 照片來源": "##### Photo Source",
    "選擇照片來源：": "Choose photo source:",
    "上傳照片": "Upload Photo",
    "拍照": "Take Photo",
    "上傳 Tesla 儀表板照片": "Upload a Tesla dashboard photo",
    "拍下 Tesla 儀表板": "Take a Tesla dashboard photo",
    "🔍 用 Gemini 擷取數值": "🔍 Extract Values with Gemini",
    "✅ 確認辨識結果": "✅ Confirm OCR Result",
    "里程 (miles)": "Odometer (miles)",
    "起始電量 %": "Starting Battery %",
    "✅ 確認並帶入": "✅ Confirm and Apply",
    "❌ 取消，重新辨識": "❌ Cancel and Scan Again",
    "##### 確認 / 輸入數值": "##### Confirm / Enter Values",
    "我已確認以上數值正確": "I confirm the values above are correct",
    "💾 確認儲存": "💾 Save Record",
    "選擇比較方式": "Select comparison mode",
    "分析指標": "Analysis metric",
    "顯示原始資料": "Show raw data",
    "選擇月份": "Select month",
    "選擇季節": "Select season",
    "選擇 ISO 週數": "Select ISO week number",
    "選擇 ISO 週": "Select ISO week",
    "選擇年份": "Select year",
    "📖 季節定義（月份對照表）": "📖 Season Definition (Month Mapping)",
    "控制變數": "Control variable",
    "季節": "Season",
    "月份": "Month",
    "季": "Quarter",
    "年份": "Year",
    "週": "Week",
    "日": "Day",
    "春季": "Spring",
    "夏季": "Summer",
    "秋季": "Fall",
    "冬季": "Winter",
    "同一季節跨年比較": "Same Season Across Years",
    "同月份跨年比較": "Same Month Across Years",
    "同月跨年比較": "Same Month Across Years",
    "同季跨年比較": "Same Quarter Across Years",
    "氣候相近季節比較": "Similar-Climate Season Comparison",
    "依年份": "By Year",
    "依季": "By Quarter",
    "依月": "By Month",
    "依週": "By Week",
    "依日": "By Day",
    "依季節": "By Season",
    "冬季跨年比較": "Winter Across Years",
    "同週跨年比較": "Same Week Across Years",
    "同一年不同月份": "Months Within the Same Year",
    "同一月不同週": "Weeks Within the Same Month",
    "同一週不同日": "Days Within the Same Week",
    "充電次數": "Charging Count",
    "平均充電間隔里程": "Average Miles Between Charges",
    "平均起始電量 %": "Average Starting Battery %",
    "平均結束電量 %": "Average Ending Battery %",
    "平均增加電量 %": "Average Battery % Added",
    "低電量充電比例": "Low-Battery Charging Rate",
    "總紀錄數": "Total Records",
    "間隔里程中位數": "Median Miles Between Charges",
    "最長間隔里程": "Longest Miles Between Charges",
    "平均起始電量": "Average Starting Battery",
    "平均結束電量": "Average Ending Battery",
    "平均增加電量": "Average Battery Added",
    "最低起始電量": "Lowest Starting Battery",
    "低電量充電次數": "Low-Battery Charging Count",
    "##### 指標總覽": "##### Indicator Overview",
    "##### 異常偵測": "##### Anomaly Detection",
    "⚙️ 閾值設定（可調整）": "⚙️ Threshold Settings",
    "充電間隔里程下降警示 (%)": "Miles-Between-Charges Drop Alert (%)",
    "低電量充電比例警示 (%)": "Low-Battery Charging Rate Alert (%)",
    "低電量定義 (%)": "Low Battery Definition (%)",
    "📝 產生綜合報告": "📝 Generate Integrated Report",
    "⬇️ 下載報告 (.md)": "⬇️ Download Report (.md)",
    "##### 📥 從 Excel / CSV 匯入": "##### 📥 Import from Excel / CSV",
    "選擇 Excel (.xlsx) 或 CSV 檔": "Choose Excel (.xlsx) or CSV file",
    "匯入模式": "Import mode",
    "附加到現有資料": "Append to existing data",
    "清除舊資料並取代": "Clear old data and replace",
    "選擇工作表": "Select worksheet",
    "👀 預覽前 10 列": "👀 Preview first 10 rows",
    "📥 匯入": "📥 Import",
    "⬇️ CSV 範本": "⬇️ CSV Template",
    "⬇️ Excel 範本": "⬇️ Excel Template",
    "##### 📤 匯出": "##### 📤 Export",
    "⬇️ 下載 CSV": "⬇️ Download CSV",
    "⬇️ 下載 Excel": "⬇️ Download Excel",
    "##### 🗃️ 瀏覽與刪除": "##### 🗃️ Browse and Delete",
    "用 record_id 刪除單筆": "Delete one record by record_id",
    "🗑️ 刪除": "🗑️ Delete",
    "⚠️ 危險區": "⚠️ Danger Zone",
    "輸入 DELETE 清空所有資料": "Type DELETE to clear all data",
    "💣 清空所有資料": "💣 Clear All Data",
    "正常": "Normal",
    "注意": "Warning",
    "警示": "Alert",
    "無資料": "No Data",
    "資料不足。": "Not enough data.",
    "無可用年份。": "No available years.",
    "無可用週數。": "No available week numbers.",
    "尚無紀錄。": "No records yet.",
    "尚無資料可匯出。": "No data to export yet.",
    "已刪除。": "Deleted.",
    "找不到該 ID。": "Could not find that ID.",
    "已清空所有資料。": "All data has been cleared.",
    "需安裝 openpyxl 才能下載 Excel。": "openpyxl is required to download Excel.",
    "讀取 Excel 需要 `openpyxl`。請執行：pip install openpyxl": "Reading Excel requires `openpyxl`. Please run: pip install openpyxl",
    "Gemini 辨識中...": "Gemini is reading the image...",
    "手動模式 — 請在下方輸入數值。": "Manual mode — please enter values below.",
    "✏️ 手動模式 — 不需要照片，直接填入下方欄位即可。": "✏️ Manual mode — no photo needed. Enter the values below.",
    "OCR 訊息：": "OCR message:",
    "距離上次充電里程：": "Miles since last charge:",
    "此次增加電量：": "Battery added this session:",
}

# Long/partial phrase replacements. Longer keys are applied first.
_EN_PHRASES = {
    "Tesla 充電健康監測 App": "Tesla Charging Health Monitor App",
    "Tesla 充電健康監測": "Tesla Charging Health Monitor",
    "電池健康代理分析": "Battery Health Proxy Analysis",
    "電池健康分析報告": "Battery Health Analysis Report",
    "充電健康分析報告": "Charging Health Analysis Report",
    "充電健康報告": "Charging Health Report",
    "充電健康監測": "Charging Health Monitor",
    "代理（proxy）分析": "proxy analysis",
    "正式 Tesla 電池診斷": "official Tesla battery diagnosis",
    "不是正式的 Tesla 電池診斷": "is not an official Tesla battery diagnosis",
    "基於里程與電量百分比行為": "based on odometer and battery-percentage behavior",
    "充電行為會受到季節影響": "charging behavior can be affected by seasonality",
    "夏天開冷氣、冬天開暖氣與電池預熱都會大幅影響耗能": "air conditioning in summer, heating in winter, and battery preconditioning can materially affect energy use",
    "比較**同一季節/同月份/同季**跨年的資料": "comparing **same-season / same-month / same-quarter** data across years",
    "可以降低季節偏差": "can reduce seasonal bias",
    "本 App 採用北半球氣候季節定義": "This app uses Northern Hemisphere climate seasons",
    "使用 Google Sheets 儲存": "Using Google Sheets storage",
    "資料會永久保存": "data will persist",
    "即使 Streamlit Cloud 重啟也不會消失": "even after Streamlit Cloud restarts",
    "使用本地 CSV 儲存": "Using local CSV storage",
    "在 Streamlit Cloud 上資料不會保存": "data will not persist on Streamlit Cloud",
    "localhost 開發模式": "localhost development mode",
    "必要欄位": "Required columns",
    "可選欄位": "Optional columns",
    "電量可為 0-1 小數或 0-100 整數": "Battery values may be decimals from 0-1 or integers from 0-100",
    "會自動偵測": "will be detected automatically",
    "請至「**新增**」分頁新增第一筆紀錄": "go to the **Add** tab to add your first record",
    "或至「**資料**」分頁匯入 Excel": "or import Excel from the **Data** tab",
    "尚無紀錄，請先匯入或新增資料": "No records yet. Please import or add data first",
    "尚無紀錄。請先匯入資料或新增充電紀錄": "No records yet. Please import data or add a charging record first",
    "尚無紀錄。請先匯入資料或新增充電紀錄。": "No records yet. Please import data or add a charging record first.",
    "本報告會**自動彙整**": "This report will **automatically consolidate**",
    "您在以下四個分頁中所做的篩選與選擇": "the filters and selections you made across the following four tabs",
    "產生一份完整的分析報告": "to generate a complete analysis report",
    "提示：先到": "Tip: first go to",
    "分頁挑好你要的篩選": "tabs to choose the filters you want",
    "再回來按下方按鈕": "then come back and click the button below",
    "總覽分頁內容": "Overview Tab Content",
    "比較分頁內容": "Comparison Tab Content",
    "控制分頁內容": "Control Tab Content",
    "健康指標": "Health Indicators",
    "五大健康指標": "Five Key Health Indicators",
    "異常偵測結果": "Anomaly Detection Results",
    "使用目前閾值未偵測到異常": "No anomalies were detected using the current thresholds",
    "以目前閾值未偵測到異常行為": "No abnormal behavior was detected using the current thresholds",
    "健康結論": "Health Conclusion",
    "建議行動": "Recommended Actions",
    "結論優先": "Conclusion First",
    "電池健康代理分析（結論優先）": "Battery Health Proxy Analysis (Conclusion First)",
    "關鍵指標": "Key Metrics",
    "圖表分析": "Chart Analysis",
    "解讀": "Interpretation",
    "總充電次數": "Total charging count",
    "平均充電間隔里程": "Average miles between charges",
    "間隔里程中位數": "Median miles between charges",
    "最長間隔里程": "Longest miles between charges",
    "平均起始電量": "Average starting battery",
    "平均結束電量": "Average ending battery",
    "平均增加電量": "Average battery added",
    "最低起始電量": "Lowest starting battery",
    "低電量充電次數": "Low-battery charging count",
    "低電量充電比例": "Low-battery charging rate",
    "里程下降警示": "miles-drop alert",
    "低電量比例警示": "low-battery rate alert",
    "低電量定義": "low-battery definition",
    "共偵測到": "Detected",
    "項紅色警示": "red alerts",
    "項黃色注意": "yellow warnings",
    "建議優先處理紅色項目": "prioritize the red items",
    "並透過控制變數比較進一步確認": "and confirm further through controlled comparisons",
    "所有指標均為正常範圍": "all indicators are within the normal range",
    "請保持目前的充電習慣": "please keep your current charging habits",
    "此外有": "Additionally, there are",
    "項異常事件": "anomaly events",
    "每年充電次數": "Annual Charging Count",
    "每年充電間隔平均里程": "Annual Average Miles Between Charges",
    "每年平均起始電量": "Annual Average Starting Battery",
    "每年平均結束電量": "Annual Average Ending Battery",
    "每月充電頻率": "Monthly Charging Frequency",
    "充電增加電量 % — 時間趨勢": "Battery % Added — Time Trend",
    "里程趨勢": "Odometer Trend",
    "日期": "Date",
    "月份": "Month",
    "年份": "Year",
    "週數": "Week Number",
    "星期": "Weekday",
    "季節": "Season",
    "平均里程": "Average miles",
    "起始電量 %": "Starting battery %",
    "結束電量 %": "Ending battery %",
    "增加電量 %": "Battery % added",
    "充電次數": "Charging count",
    "平均間隔里程": "Average miles between charges",
    "溫和季節": "mild season",
    "春季": "Spring",
    "夏季": "Summer",
    "秋季": "Fall",
    "冬季": "Winter",
    "依年份": "By year",
    "依季": "By quarter",
    "依月": "By month",
    "依週": "By week",
    "依日": "By day",
    "依季節": "By season",
    "同一季節跨年比較": "same-season comparison across years",
    "同月份跨年比較": "same-month comparison across years",
    "同月跨年比較": "same-month comparison across years",
    "同季跨年比較": "same-quarter comparison across years",
    "氣候相近季節比較": "similar-climate season comparison",
    "跨年比較": "comparison across years",
    "跨年": "across years",
    "資料不足": "not enough data",
    "無資料": "no data",
    "尚無紀錄": "no records yet",
    "找不到": "could not find",
    "紀錄已儲存": "record saved",
    "暫存照片已刪除": "temporary photos deleted",
    "儀表板已更新": "dashboard updated",
    "已載入": "loaded",
    "成功匯入": "successfully imported",
    "跳過": "skipped",
    "無資料匯入": "no data imported",
    "讀取失敗": "read failed",
    "開啟 Google Sheets 試算表": "Open Google Sheets spreadsheet",
    "從上方表格複製 ID 貼到這裡": "Copy an ID from the table above and paste it here",
    "前期平均": "earlier average",
    "近期平均": "recent average",
    "充電頻率": "charging frequency",
    "充電間隔里程": "miles between charges",
    "頻繁深度放電": "frequent deep discharge",
    "起始電量行為": "starting-battery behavior",
    "電量增加與里程比例": "battery-added versus miles ratio",
    "季節調整趨勢": "seasonally adjusted trend",
    "需要至少兩年的同一季資料才能比較": "needs at least two years of data for the same season to compare",
    "電量充足時就充電": "charging while the battery is still sufficient",
    "對電池壽命友善": "is battery-life friendly",
    "建議提高至 20% 以上": "consider raising it above 20%",
    "Tesla 建議日常 80% 即可": "Tesla generally recommends 80% for daily use",
    "結束電量在 Tesla 建議範圍內": "ending battery is within Tesla's recommended range",
    "曲線斜率反映駕駛強度的變化": "the line slope reflects changes in driving intensity",
    "若此數值持續上升而間隔里程沒同步增加，可能反映效率下降": "if this keeps rising without a corresponding increase in miles between charges, it may indicate lower efficiency",
    "避免低電量": "Avoid low battery",
    "才充電": "before charging",
    "持續記錄": "Continue recording",
    "能讓代理分析更精準": "to make proxy analysis more accurate",
    "未來若能加入": "If future data can include",
    "可做真正效率分析": "true efficiency analysis can be performed",
    "持續追蹤": "Continue tracking",
    "是否下降": "whether it is declining",
    "控制變數後表現穩定": "stable after controlling variables",
    "控制季節後表現穩定或改善": "stable or improved after controlling seasonality",
    "在同季節跨年下仍下降明顯": "still declines materially in same-season comparisons",
    "排除季節因素後的退化更值得注意": "degradation after removing seasonality is more worth attention",
    "輕微下降": "slight decline",
    "可持續追蹤": "keep tracking it",
    "上升": "increasing",
    "下降": "declining",
    "持平": "flat",
    "明顯上升": "significant increase",
    "略為上升": "slight increase",
    "明顯下降": "significant decrease",
    "略為下降": "slight decrease",
    "輕度": "light",
    "中度": "moderate",
    "高度": "heavy",
    "使用": "use",
    "筆數": "records",
    "筆": "records",
    "列": "rows",
    "個問題": "issues",
    "未顯示": "not shown",
    "第": "Figure ",
    "圖": "Chart",
    "同": "same",
}


def _simplify(text: str) -> str:
    out = text
    for k, v in sorted(_ZH_CN_PHRASES.items(), key=lambda item: len(item[0]), reverse=True):
        out = out.replace(k, v)
    out = out.translate(_ZH_CN_CHARS)
    return out


def _english(text: str) -> str:
    if text in _EN_EXACT:
        return _EN_EXACT[text]
    out = text
    for k, v in sorted(_EN_PHRASES.items(), key=lambda item: len(item[0]), reverse=True):
        out = out.replace(k, v)
    return out


def translate_text(value: Any, lang: str | None = None) -> Any:
    """Translate strings. Non-strings are returned unchanged."""
    if not isinstance(value, str):
        return value
    lang = lang or current_language()
    if lang == "zh-TW":
        return value
    if lang == "zh-CN":
        return _simplify(value)
    if lang == "en":
        return _english(value)
    return value


# Alias used by app code
tr = translate_text


def translate_option(option: Any, lang: str | None = None) -> str:
    """Translate display text while preserving the original option value."""
    return str(translate_text(str(option), lang=lang))


def translate_dataframe_for_display(obj: Any, lang: str | None = None) -> Any:
    try:
        import pandas as pd  # type: ignore
        if isinstance(obj, pd.DataFrame):
            df = obj.copy()
            df.columns = [translate_text(str(c), lang=lang) for c in df.columns]
            return df
    except Exception:
        pass
    return obj


def translate_plotly_figure(fig: Any, lang: str | None = None) -> Any:
    """Translate Plotly titles and axis labels in-place when possible."""
    try:
        fig = copy.deepcopy(fig)
        layout = fig.layout

        if getattr(layout, "title", None) is not None and getattr(layout.title, "text", None):
            layout.title.text = translate_text(layout.title.text, lang)

        for axis_name in ["xaxis", "yaxis", "xaxis2", "yaxis2"]:
            axis = getattr(layout, axis_name, None)
            if axis is not None and getattr(axis, "title", None) is not None:
                if getattr(axis.title, "text", None):
                    axis.title.text = translate_text(axis.title.text, lang)

        # Annotation text, including empty chart messages.
        if getattr(layout, "annotations", None):
            for ann in layout.annotations:
                if getattr(ann, "text", None):
                    ann.text = translate_text(ann.text, lang)
        return fig
    except Exception:
        return fig


def _wrap_text_first_arg(fn, index: int = 0):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        args = list(args)
        if len(args) > index:
            args[index] = translate_text(args[index])
        # Common keyword label/title/body arguments
        for key in ("label", "body", "text", "title", "help", "placeholder"):
            if key in kwargs:
                kwargs[key] = translate_text(kwargs[key])
        return fn(*args, **kwargs)
    return wrapper


def patch_streamlit(st: Any) -> None:
    """Patch selected Streamlit render functions for automatic display translation."""
    if getattr(st, "_tesla_i18n_patched", False):
        return

    # Simple text-display APIs.
    for name in [
        "title", "header", "subheader", "caption", "markdown", "write",
        "success", "warning", "error", "info", "toast", "text", "code",
    ]:
        if hasattr(st, name):
            setattr(st, name, _wrap_text_first_arg(getattr(st, name)))

    # Spinner has first text arg.
    if hasattr(st, "spinner"):
        st.spinner = _wrap_text_first_arg(st.spinner)

    # Dialog title.
    if hasattr(st, "dialog"):
        st.dialog = _wrap_text_first_arg(st.dialog)

    # Expander label.
    if hasattr(st, "expander"):
        st.expander = _wrap_text_first_arg(st.expander)

    # Button-like and input labels.
    for name in [
        "button", "download_button", "text_input", "text_area",
        "number_input", "date_input", "slider", "checkbox",
        "file_uploader",
    ]:
        if hasattr(st, name):
            setattr(st, name, _wrap_text_first_arg(getattr(st, name)))

    # Tabs: translate labels only.
    if hasattr(st, "tabs"):
        _orig_tabs = st.tabs

        @wraps(_orig_tabs)
        def tabs_wrapper(tabs, *args, **kwargs):
            return _orig_tabs([translate_text(x) for x in tabs], *args, **kwargs)

        st.tabs = tabs_wrapper

    # Selectbox / radio / multiselect: preserve original values, translate display.
    for name in ["selectbox", "radio", "multiselect"]:
        if hasattr(st, name):
            orig = getattr(st, name)

            @wraps(orig)
            def choice_wrapper(label, options=None, *args, __orig=orig, **kwargs):
                label = translate_text(label)
                original_format = kwargs.get("format_func")
                if original_format is None:
                    kwargs["format_func"] = lambda x: translate_option(x)
                else:
                    kwargs["format_func"] = lambda x, _fmt=original_format: translate_text(str(_fmt(x)))
                return __orig(label, options, *args, **kwargs)

            setattr(st, name, choice_wrapper)

    # Metric labels.
    if hasattr(st, "metric"):
        _orig_metric = st.metric

        @wraps(_orig_metric)
        def metric_wrapper(label, value, delta=None, *args, **kwargs):
            return _orig_metric(translate_text(label), value, translate_text(delta) if isinstance(delta, str) else delta, *args, **kwargs)

        st.metric = metric_wrapper

    # Plotly charts.
    if hasattr(st, "plotly_chart"):
        _orig_plotly_chart = st.plotly_chart

        @wraps(_orig_plotly_chart)
        def plotly_wrapper(fig, *args, **kwargs):
            return _orig_plotly_chart(translate_plotly_figure(fig), *args, **kwargs)

        st.plotly_chart = plotly_wrapper

    # Dataframe/table display columns.
    for name in ["dataframe", "table"]:
        if hasattr(st, name):
            orig = getattr(st, name)

            @wraps(orig)
            def df_wrapper(data=None, *args, __orig=orig, **kwargs):
                return __orig(translate_dataframe_for_display(data), *args, **kwargs)

            setattr(st, name, df_wrapper)

    st._tesla_i18n_patched = True
