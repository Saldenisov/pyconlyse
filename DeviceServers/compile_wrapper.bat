@echo off
REM =====================================================
REM Compile DS_Basler_camera C# Wrapper to Executable
REM =====================================================

echo =====================================================
echo Compiling DS_Basler_camera C# Wrapper
echo =====================================================

REM Check if .NET Framework is available
where csc >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: C# compiler (csc.exe) not found in PATH!
    echo Please install .NET Framework SDK or Visual Studio
    echo Trying common .NET Framework locations...
    
    REM Try common .NET Framework paths
    set "DOTNET_PATH="
    if exist "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" (
        set "DOTNET_PATH=C:\Windows\Microsoft.NET\Framework64\v4.0.30319"
    ) else if exist "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe" (
        set "DOTNET_PATH=C:\Windows\Microsoft.NET\Framework\v4.0.30319"
    )
    
    if defined DOTNET_PATH (
        echo Found .NET Framework at: %DOTNET_PATH%
        set "PATH=%DOTNET_PATH%;%PATH%"
    ) else (
        echo ERROR: Could not locate .NET Framework compiler!
        echo Please install .NET Framework SDK
        pause
        exit /b 1
    )
)

REM Compile the C# source to executable
echo Compiling DS_Basler_camera_wrapper.cs...
csc /out:DS_Basler_camera.exe /target:exe DS_Basler_camera_wrapper.cs

if %errorlevel% neq 0 (
    echo ERROR: DS_Basler_camera compilation failed!
    pause
    exit /b 1
)

if exist DS_LaserPointing_wrapper.cs (
    echo.
    echo Compiling DS_LaserPointing_wrapper.cs...
    csc /out:DS_LaserPointing.exe /target:exe DS_LaserPointing_wrapper.cs
    
    if %errorlevel% neq 0 (
        echo ERROR: DS_LaserPointing compilation failed!
        pause
        exit /b 1
    )
    echo ✓ DS_LaserPointing.exe created successfully!
)

if exist DS_Netio_pdu_wrapper.cs (
    echo.
    echo Compiling DS_Netio_pdu_wrapper.cs...
    csc /out:DS_Netio_pdu.exe /target:exe DS_Netio_pdu_wrapper.cs
    
    if %errorlevel% neq 0 (
        echo ERROR: DS_Netio_pdu compilation failed!
        pause
        exit /b 1
    )
    echo ✓ DS_Netio_pdu.exe created successfully!
)

echo.
echo ✓ Compilation successful!
echo ✓ Created: DS_Basler_camera.exe
echo.
echo The executable is now ready for use with Astor.
echo You can test it manually by running:
echo   DS_Basler_camera.exe 1_Cam1_V0
echo.

pause