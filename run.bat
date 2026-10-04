@echo off
title TickerPing - Stock Price Alarmer
echo ===================================================
echo           TickerPing Stock Alarmer
echo ===================================================
echo Starting local web server...
echo Access dashboard at: http://localhost:8000
echo.

python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
pause
