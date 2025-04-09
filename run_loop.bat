@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat

for /L %%i in (1,1,10) do (
    echo Run %%i of 10
    python main.py
    echo Finished run %%i
    echo ================
    timeout /t 5
)

pause