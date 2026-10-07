@echo off
chcp 65001 >nul
rem 바탕화면에 [도면분석기] 바로가기 생성 — PC마다 1회 실행
set "HERE=%~dp0"
set "TARGET=%HERE%도면분석_실행.bat"
if not exist "%TARGET%" (
  echo [오류] 도면분석_실행.bat 을 찾을 수 없습니다.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $d=$w.SpecialFolders('Desktop'); $s=$w.CreateShortcut((Join-Path $d '도면분석기.lnk')); $s.TargetPath=$env:TARGET; $s.WorkingDirectory=$env:HERE; $s.IconLocation='%SystemRoot%\System32\imageres.dll,68'; $s.Description='도면 판독 - 건축/기계/전기/소방/정보통신 (도면 폴더를 끌어다 놓으세요)'; $s.Save()"
echo.
echo  바탕화면에 [도면분석기] 바로가기를 만들었습니다.
echo  도면이 든 폴더를 그 아이콘 위에 끌어다 놓으면 바로 분석이 시작됩니다.
echo.
pause
