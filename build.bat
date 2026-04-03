@echo off
echo ============================================================
echo Hydraulic Analysis Tool - Build Script
echo ============================================================
echo.

REM Check Python is available
python --version 2>NUL
if errorlevel 1 (
    echo ERROR: Python not found on PATH
    exit /b 1
)

REM Check PyInstaller is available
python -m PyInstaller --version 2>NUL
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Building application...
echo.

pyinstaller hydraulic_tool.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo BUILD FAILED
    exit /b 1
)

echo.
echo ============================================================
echo BUILD SUCCESSFUL
echo Output: dist\HydraulicAnalysisTool\
echo Run:    dist\HydraulicAnalysisTool\HydraulicAnalysisTool.exe
echo ============================================================
