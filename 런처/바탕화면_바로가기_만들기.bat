@echo off
chcp 65001 >nul
rem 바탕화면에 [기계설비·정보통신 문서자동화 런처] 바로가기 생성 — 지점 PC에서 1회 실행
set "HERE=%~dp0..\"
set "TARGET=%HERE%기계설비_정보통신_런처.bat"
if not exist "%TARGET%" (
  echo [오류] 기계설비_정보통신_런처.bat 을 찾을 수 없습니다.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $d=$w.SpecialFolders('Desktop'); $s=$w.CreateShortcut((Join-Path $d '기계설비·정보통신 문서자동화 런처.lnk')); $s.TargetPath=$env:TARGET; $s.WorkingDirectory=$env:HERE; $s.IconLocation='%SystemRoot%\System32\shell32.dll,14'; $s.Description='기계설비 / 정보통신 문서자동화 웹 런처'; $s.Save()"
echo.
echo  바탕화면에 [기계설비·정보통신 문서자동화 런처] 바로가기를 만들었습니다.
echo.
pause
