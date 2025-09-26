@echo off
REM Tango Tools Launcher Menu
REM Quick access to all Tango applications

echo.
echo ========================================
echo    TANGO CONTROLS - TOOLS LAUNCHER
echo ========================================
echo.
echo Available tools:
echo   [1] Astor   - Administration Tool
echo   [2] Jive    - Database Configuration
echo   [3] ATK     - Application Toolkit Demo
echo   [4] Exit
echo.
set /p choice="Select tool (1-4): "

if "%choice%"=="1" goto astor
if "%choice%"=="2" goto jive  
if "%choice%"=="3" goto atk
if "%choice%"=="4" goto exit
echo Invalid choice!
pause
goto menu

:astor
echo Starting Astor...
"C:\tools\jdk-17.0.2\bin\java" -jar "C:\dev\astor\target\Astor-7.6.1-SNAPSHOT-jar-with-dependencies.jar"
goto exit

:jive
echo Starting Jive...
"C:\tools\jdk-17.0.2\bin\java" -jar "C:\dev\jive\target\Jive-7.46-SNAPSHOT-jar-with-dependencies.jar"
goto exit

:atk
echo Starting ATK Demo...
"C:\tools\jdk-17.0.2\bin\java" -cp "C:\dev\atk\widget\target\ATKWidget-9.4.15-SNAPSHOT.jar;C:\dev\atk\core\target\ATKCore-9.4.15-SNAPSHOT.jar" fr.esrf.tangoatk.widget.util.ATKMain
goto exit

:exit