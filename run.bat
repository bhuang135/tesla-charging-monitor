@echo off
chcp 65001 >nul
REM ============================================================
REM  Tesla 充電健康監測 — 一鍵啟動腳本 (Windows)
REM ============================================================

cd /d "%~dp0"

echo.
echo === Tesla 充電健康監測 ===
echo.
echo 工作目錄： %CD%
echo.

REM --- 確認結構 ---
if not exist "app.py" (
    echo [錯誤] 找不到 app.py
    echo 請從 Tesla 專案資料夾內執行此腳本。
    pause
    exit /b 1
)
if not exist "modules\" (
    echo [錯誤] 缺少 modules\ 資料夾。
    echo 請確認 zip 已完整解壓縮，結構應為：
    echo.
    echo   Tesla\
    echo     app.py
    echo     modules\
    echo       __init__.py
    echo       data_store.py
    echo       ...
    pause
    exit /b 1
)
if not exist "modules\__init__.py" (
    echo [警告] 缺少 modules\__init__.py，自動建立中...
    type nul > "modules\__init__.py"
)

REM --- 確認 python ---
where python >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 沒有偵測到 Python。
    echo 請至 https://www.python.org/downloads/ 安裝 Python 3.10+
    echo 並在安裝時勾選「Add Python to PATH」。
    pause
    exit /b 1
)

REM --- 第一次執行時安裝套件 ---
if not exist ".deps_installed" (
    echo 第一次執行，正在安裝套件（需要幾分鐘）...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [錯誤] pip install 失敗。請查看上方錯誤訊息。
        pause
        exit /b 1
    )
    echo. > .deps_installed
    echo 完成。
    echo.
)

REM --- 啟動 ---
echo 啟動 Streamlit，瀏覽器會自動開啟。
echo 按 Ctrl+C 結束伺服器。
echo.
python -m streamlit run app.py

pause
