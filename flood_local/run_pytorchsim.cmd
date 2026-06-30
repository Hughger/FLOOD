@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_pytorchsim.ps1" %*
exit /b %ERRORLEVEL%
