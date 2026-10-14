@echo off
cd /d "C:\Users\howlil\Documents\Projects\job"
set PYTHONPATH=apps\api
"C:\Users\howlil\AppData\Local\Programs\Python\Python312\python.exe" -m jobhunt run >> "C:\Users\howlil\Documents\Projects\job\data\cron.log" 2>&1
