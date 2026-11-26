@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYCMD="
py -3.12 -c "import sys" >nul 2>nul && set "PYCMD=py -3.12"
if not defined PYCMD py -3 -c "import sys" >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD python -c "import sys" >nul 2>nul && set "PYCMD=python"

if not defined PYCMD (
  echo.
  echo [RepoReady][ERROR] Python 3.11+ was not found.
  echo Install Python 3.12: https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
%PYCMD% "%~dp0scripts\start.py" %*
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" pause
exit /b %EXITCODE%
