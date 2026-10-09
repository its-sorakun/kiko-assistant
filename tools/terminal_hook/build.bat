@echo off
echo [*] Freeing PowerShell from the IFEO infinite loop...
reg delete "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\powershell.exe" /v Debugger /f

echo [*] Locating MSVC via vswhere...
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -property installationPath`) do set InstallDir=%%i

echo [*] Initializing MSVC Developer Command Prompt...
call "%InstallDir%\VC\Auxiliary\Build\vcvars64.bat"

cd /d "D:\codih\assistant\tools\terminal_hook"

echo [*] Attempting to free locked DLLs...
if exist hook.dll move /y hook.dll hook_old_%RANDOM%.dll >nul 2>&1

echo [*] Compiling Hook DLL...
cl /LD hook.cpp /link ws2_32.lib /OUT:hook.dll
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to compile hook.dll!
    pause
    exit /b %ERRORLEVEL%
)

echo [*] Compiling Injector EXE...
cl injector.cpp /OUT:injector.exe

echo [*] Cleaning up MSVC artifacts...
del *.obj *.lib *.exp

echo [*] Re-enabling IFEO Hook...
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\powershell.exe" /v Debugger /t REG_SZ /d "D:\codih\assistant\tools\terminal_hook\injector.exe" /f

echo [SUCCESS] Everything is compiled and re-hooked! You can now open a normal PowerShell window.
pause
