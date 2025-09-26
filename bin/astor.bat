@echo off
REM Astor Launcher Script
REM Launches the latest Astor Tango Administration Tool

echo Starting Astor...
"C:\tools\jdk-17.0.2\bin\java" -jar "C:\dev\astor\target\Astor-7.6.1-SNAPSHOT-jar-with-dependencies.jar" %*
