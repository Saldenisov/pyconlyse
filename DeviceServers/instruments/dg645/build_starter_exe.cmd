@echo off
setlocal

if "%PYCONLYSE%"=="" set "PYCONLYSE=C:\dev\pyconlyse"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

"%CSC%" /nologo /target:exe /out:"%PYCONLYSE%\DeviceServers\DS_DG645.exe" "%PYCONLYSE%\DeviceServers\instruments\dg645\DS_DG645_launcher.cs"

endlocal
