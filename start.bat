@echo off
chcp 65001 >nul
echo ========================================
echo   Учёт замечаний — запуск приложения
echo ========================================
echo.

cd /d "%~dp0"

if not exist "backend\venv" (
    echo [1/4] Создание виртуального окружения Python...
    python -m venv backend\venv
)

echo [2/4] Установка зависимостей backend...
call backend\venv\Scripts\activate.bat
pip install -r backend\requirements.txt -q

if not exist "frontend\node_modules" (
    echo [3/4] Установка зависимостей frontend...
    cd frontend
    call npm install
    cd ..
) else (
    echo [3/4] Frontend зависимости уже установлены
)

echo [4/4] Запуск серверов...
echo.
echo Локально:   http://127.0.0.1:5173
echo В сети:     http://%COMPUTERNAME%:5173
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    echo             http://%%a:5173
)
echo.
echo Backend API: порт 8000 (доступен через frontend)
echo.
echo Для остановки закройте окна терминалов.
echo Если с другого ПК не открывается — разрешите порты 5173 и 8000 в брандмауэре Windows.
echo.

start "Backend" cmd /k "cd /d %~dp0backend && call ..\backend\venv\Scripts\activate.bat && uvicorn main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 2 /nobreak >nul
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo Готово.
pause
