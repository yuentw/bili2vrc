@echo off
chcp 65001 >nul
echo [bili2vrchat] 啟動中...

:: 安裝依賴（首次使用）
python -m pip install -r requirements.txt -q

:: 啟動服務
python app.py

pause
