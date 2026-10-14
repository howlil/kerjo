@echo off
setlocal
cd /d "%~dp0.."
if not exist data mkdir data
set PYTHONPATH=apps\api
python -m jobhunt run >> data\cron.log 2>&1
exit /b %errorlevel%
