@echo off
rem Gus_Rigtool real-Maya tests (5.6.35): double-click. Writes maya_test_results.txt next to this file.
setlocal
set "HERE=%~dp0"
set "CFG=%USERPROFILE%\gus_maya_tests_mayapy.txt"
set "MAYAPY=C:\Program Files\Autodesk\Maya2024\bin\mayapy.exe"
if exist "%CFG%" set /p MAYAPY=<"%CFG%"
if exist "%MAYAPY%" goto run
echo Maya's mayapy.exe isn't at: %MAYAPY%
echo Find it in your Maya folder (Maya2024\bin\mayapy.exe), drag it into this window and press Enter.
set /p MAYAPY=mayapy.exe: 
set MAYAPY=%MAYAPY:"=%
if not exist "%MAYAPY%" goto missing
> "%CFG%" echo %MAYAPY%
:run
echo Using %MAYAPY%
"%MAYAPY%" "%HERE%run_maya_tests.py" %*
echo.
pause
exit /b 0
:missing
echo Still not found - nothing was run.
pause
exit /b 1
