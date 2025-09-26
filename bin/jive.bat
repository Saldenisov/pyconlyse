@echo off
REM Jive Launcher Script
REM Launches Jive Database Configuration Tool

echo Starting Jive...
"C:\tools\jdk-17.0.2\bin\java" -jar "C:\dev\jive\target\Jive-7.46-SNAPSHOT-jar-with-dependencies.jar" %*
