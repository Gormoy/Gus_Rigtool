@echo off
rem Onion Skin - the test in real Maya: double-click. Writes tests\onion_test_results.txt.
setlocal
set "HERE=%~dp0"
set "CFG=%USERPROFILE%\onion_skin_mayapy.txt"
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
"%MAYAPY%" "%HERE%tests\test_in_maya.py"
echo.
pause
exit /b 0
:missing
echo Still not found - nothing was run.
pause
exit /b 1
