@echo off
setlocal

if "%PYCONLYSE%"=="" set "PYCONLYSE=C:\dev\pyconlyse"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

echo ERROR: DS_DG645.exe is intentionally removed; use DS_DG645.bat.
exit /b 1

endlocal
