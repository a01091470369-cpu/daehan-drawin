@echo off
chcp 65001 >nul
title 도면분석기
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ============================================================
echo         도 면 분 석 기   -  건축 · 기계 · 전기 · 소방 · 정보통신
echo ============================================================
echo.

set "FOLDER=%~1"
if not defined FOLDER (
  echo   도면이 든 폴더를 이 창에 끌어다 놓거나 경로를 붙여넣고 Enter 하세요.
  echo   ^(취소하려면 그냥 Enter^)
  echo.
  set /p FOLDER="   도면 폴더 : "
)
if not defined FOLDER goto :fin
set FOLDER=%FOLDER:"=%

if not exist "%FOLDER%\" (
  echo.
  echo   [오류] 폴더를 찾을 수 없습니다: %FOLDER%
  echo.
  pause
  exit /b 1
)

for %%I in ("%FOLDER%") do set "DEFNAME=%%~nxI"
echo.
set "NAME="
set /p NAME="   건물명 (그냥 Enter 하면 %DEFNAME%) : "
if not defined NAME set "NAME=%DEFNAME%"

echo.
echo ------------------------------------------------------------
python "analyze.py" "%FOLDER%" --name "%NAME%"
set "rc=%errorlevel%"
echo ------------------------------------------------------------
echo.

if not "%rc%"=="0" (
  echo   [오류] 전처리에 실패했습니다. ^(코드 %rc%^)
  echo.
  pause
  exit /b %rc%
)

echo   전처리가 끝났습니다. 이제 Claude 에게 이렇게 말하세요:
echo.
echo        "%NAME% 도면 판독해줘"
echo.
echo   Claude 가 추출된 도면을 직접 보고 설비목록과 검토보고서를 만듭니다.
echo.
set "ANS="
set /p ANS="   작업 폴더를 열어볼까요? (Y/N) : "
if /i "%ANS%"=="Y" start "" "%~dp0작업\%NAME%"

:fin
echo.
pause
