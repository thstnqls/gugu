@echo off
REM ============================================================
REM  GUGU Windows 빌드 스크립트
REM  Python 3.10+ 가 PATH에 있어야 합니다.
REM  더블클릭으로 실행 → dist\GUGU\GUGU.exe 생성
REM ============================================================
setlocal
cd /d "%~dp0"

echo [GUGU] Python 확인...
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python 이 PATH 에 없습니다.
    echo   https://www.python.org/downloads/windows/ 에서 3.10 이상 설치
    echo   설치 시 "Add python.exe to PATH" 반드시 체크
    echo.
    pause
    exit /b 1
)

echo [GUGU] 가상환경 준비...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] venv 생성 실패
        pause
        exit /b 1
    )
)

echo [GUGU] 의존성 설치...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [ERROR] pip install 실패
    pause
    exit /b 1
)

echo [GUGU] 이전 빌드 정리...
if exist "build\GUGU" rmdir /s /q "build\GUGU"
if exist "dist\GUGU"  rmdir /s /q "dist\GUGU"

echo [GUGU] PyInstaller 실행...
".venv\Scripts\pyinstaller.exe" GUGU-win.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller 실패
    pause
    exit /b 1
)

if not exist "dist\GUGU\GUGU.exe" (
    echo [ERROR] GUGU.exe 가 생성되지 않았습니다.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  완료! dist\GUGU\GUGU.exe 더블클릭으로 실행하세요.
echo  배포 시엔 dist\GUGU 폴더 전체를 zip 으로 묶어 전달.
echo ============================================================
echo.
pause
endlocal
