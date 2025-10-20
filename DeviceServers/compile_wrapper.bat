@echo off
REM =====================================================
REM Compile DeviceServer C# Wrappers to Executables
REM =====================================================

echo =====================================================
echo Compiling DeviceServer C# Wrappers
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

REM Compile Basler wrapper
echo Compiling DS_Basler_camera_wrapper.cs...
csc /out:DS_Basler_camera.exe /target:exe DS_Basler_camera_wrapper.cs
if %errorlevel% neq 0 (
    echo ERROR: DS_Basler_camera compilation failed!
    pause
    exit /b 1
)

echo.
REM Compile LaserPointing wrapper if present
if exist DS_LaserPointing_wrapper.cs (
    echo Compiling DS_LaserPointing_wrapper.cs...
    csc /out:DS_LaserPointing.exe /target:exe DS_LaserPointing_wrapper.cs
    if %errorlevel% neq 0 (
        echo ERROR: DS_LaserPointing compilation failed!
        pause
        exit /b 1
    )
    echo ✓ DS_LaserPointing.exe created successfully!
)

echo.
REM Compile Netio PDU wrapper if present
if exist DS_Netio_pdu_wrapper.cs (
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
REM Compile OWIS wrapper if present
if exist DS_OWIS_PS90_wrapper.cs (
    echo Compiling DS_OWIS_PS90_wrapper.cs...
    csc /out:DS_OWIS_PS90.exe /target:exe DS_OWIS_PS90_wrapper.cs
    if %errorlevel% neq 0 (
        echo ERROR: DS_OWIS_PS90 compilation failed!
        pause
        exit /b 1
    )
    echo ✓ DS_OWIS_PS90.exe created successfully!
)

echo.
REM Compile Standa wrapper if present
if exist DS_Standa_Motor_wrapper.cs (
    echo Compiling DS_Standa_Motor_wrapper.cs...
    csc /out:DS_Standa_Motor.exe /target:exe DS_Standa_Motor_wrapper.cs
    if %errorlevel% neq 0 (
        echo ERROR: DS_Standa_Motor compilation failed!
        pause
        exit /b 1
    )
    echo ✓ DS_Standa_Motor.exe created successfully!
)

echo.
REM Compile Keysight 33509B wrapper if present
if exist DS_KEYSIGHT_33509B_wrapper.cs (
    echo Compiling DS_KEYSIGHT_33509B_wrapper.cs...
    csc /out:DS_KEYSIGHT_33509B.exe /target:exe DS_KEYSIGHT_33509B_wrapper.cs
    if %errorlevel% neq 0 (
        echo ERROR: DS_KEYSIGHT_33509B compilation failed!
        pause
        exit /b 1
    )
    echo ✓ DS_KEYSIGHT_33509B.exe created successfully!
)

echo.
REM Compile iTest PSU wrapper if present
if exist DS_iTest_PSU_wrapper.cs (
    echo Compiling DS_iTest_PSU_wrapper.cs...
    csc /out:DS_iTest_PSU.exe /target:exe DS_iTest_PSU_wrapper.cs
    if %errorlevel% neq 0 (
        echo ERROR: DS_iTest_PSU compilation failed!
        pause
        exit /b 1
    )
    echo ✓ DS_iTest_PSU.exe created successfully!
)

echo.
REM Compile ML Stability wrapper if present
if exist DS_ML_Stability_wrapper.cs (
    echo Compiling DS_ML_Stability_wrapper.cs...
    csc /out:DS_ML_Stability.exe /target:exe DS_ML_Stability_wrapper.cs
    if %errorlevel% neq 0 (
        echo ERROR: DS_ML_Stability compilation failed!
        pause
        exit /b 1
    )
    echo ✓ DS_ML_Stability.exe created successfully!
)

echo.
echo ✓ Compilation successful!
echo ✓ Created/updated wrappers where sources were present.
echo.
echo The executables are now ready for use with Astor.
echo Example: DS_iTest_PSU.exe 1_iTest
echo.

pause
